from datetime import UTC, datetime

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import kb_entries
from app.kb.embeddings import MEANING_FLOOR, MODEL_NAME
from app.kb.model import Entry
from app.kb.text import fts_query

CANDIDATES = 20  # per search method, before the two rankings are merged
RRF_K = 60  # the usual reciprocal rank fusion constant: rank matters, raw scores don't


def _aware(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo:
        return value
    return value.replace(tzinfo=UTC)


def _to_entry(row, similarity: float | None = None) -> Entry:
    return Entry(
        id=row.id,
        text=row.text,
        topic=row.topic,
        kind=row.kind,
        place_id=row.place_id,
        country=row.country,
        attributes=row.attributes or {},
        source_url=row.source_url,
        source_title=row.source_title,
        source_tier=row.source_tier,
        lang=row.lang,
        published_at=row.published_at,
        fetched_at=_aware(row.fetched_at),
        valid_until=_aware(row.valid_until),
        created_by=row.created_by,
        status=row.status,
        query=row.query,
        similarity=similarity,
    )


async def add_entries(
    db: AsyncSession, entries: list[Entry], vectors: list[list[float]] | None = None
) -> list[int]:
    """Writes new entries and indexes them. An exact duplicate (same text) keeps the stored one, but a
    re-fetch refreshes its dates, so a fact seen again today counts as fresh. Returns the ids.
    Without vectors the entries are found by words only until backfill_embeddings catches up."""
    ids: list[int] = []
    for index, entry in enumerate(entries):
        existing = (
            await db.execute(select(kb_entries.c.id).where(kb_entries.c.content_hash == entry.hash))
        ).scalar()
        if existing is not None:
            await db.execute(
                update(kb_entries)
                .where(kb_entries.c.id == existing)
                .values(fetched_at=entry.fetched_at, valid_until=entry.valid_until, status="active")
            )
            ids.append(existing)
            continue
        result = await db.execute(
            kb_entries.insert().values(
                text=entry.text,
                topic=entry.topic,
                kind=entry.kind,
                place_id=entry.place_id,
                country=entry.country,
                entities=entry.entities,
                attributes=entry.attributes,
                source_url=entry.source_url,
                source_title=entry.source_title,
                source_tier=entry.source_tier,
                confidence=entry.confidence,
                lang=entry.lang,
                published_at=entry.published_at,
                fetched_at=entry.fetched_at,
                valid_until=entry.valid_until,
                content_hash=entry.hash,
                created_by=entry.created_by,
                status=entry.status,
                query=entry.query,
                embedding=vectors[index] if vectors else None,
                embedding_model=MODEL_NAME if vectors else None,
            )
        )
        ids.append(result.inserted_primary_key[0])
    return ids


def fuse_rankings(*rankings: list[int]) -> list[int]:
    """Reciprocal rank fusion: an entry near the top of both lists beats one that tops only one.
    On a tie the earlier list wins, so pass the more trusted ranking first."""
    scores: dict[int, float] = {}
    first_seen: dict[int, tuple[int, int]] = {}
    for list_index, ranking in enumerate(rankings):
        for position, entry_id in enumerate(ranking, start=1):
            scores[entry_id] = scores.get(entry_id, 0.0) + 1 / (RRF_K + position)
            first_seen.setdefault(entry_id, (list_index, position))
    return sorted(scores, key=lambda entry_id: (-scores[entry_id], first_seen[entry_id], entry_id))


def _filters(now: datetime, place_id, country, topics, fresh_only: bool) -> list:
    conditions = [kb_entries.c.status == "active"]
    scope = []
    if place_id:
        scope.append(kb_entries.c.place_id == place_id)
    if country:
        scope.append(and_(kb_entries.c.country == country, kb_entries.c.place_id.is_(None)))
    if scope:
        conditions.append(or_(*scope))
    if topics:
        conditions.append(kb_entries.c.topic.in_(topics))
    if fresh_only:
        conditions.append(or_(kb_entries.c.valid_until.is_(None), kb_entries.c.valid_until > now))
    return conditions


async def _by_words(db: AsyncSession, query: str, conditions: list) -> list[int]:
    match = fts_query(query)
    if match is None:
        return []
    tsquery = func.to_tsquery("simple", match)
    ranked = (
        select(kb_entries.c.id)
        .where(kb_entries.c.search.op("@@")(tsquery), *conditions)
        .order_by(func.ts_rank_cd(kb_entries.c.search, tsquery).desc(), kb_entries.c.id)
        .limit(CANDIDATES)
    )
    return list((await db.execute(ranked)).scalars())


async def _by_meaning(db: AsyncSession, vector: list[float] | None, conditions: list) -> dict[int, float]:
    if vector is None:
        return {}
    distance = kb_entries.c.embedding.cosine_distance(vector)
    nearest = (
        select(kb_entries.c.id, distance.label("distance"))
        .where(kb_entries.c.embedding.is_not(None), distance <= 1 - MEANING_FLOOR, *conditions)
        .order_by(distance, kb_entries.c.id)
        .limit(CANDIDATES)
    )
    return {row.id: 1 - row.distance for row in (await db.execute(nearest)).all()}


async def search(
    db: AsyncSession,
    query: str,
    now: datetime,
    place_id: str | None = None,
    country: str | None = None,
    topics: list[str] | None = None,
    fresh_only: bool = True,
    limit: int = 6,
    query_vector: list[float] | None = None,
) -> list[Entry]:
    """Filter exactly (place or country, topic, status, freshness), then rank by words and, given a query
    vector, by meaning, merging both. A place filter also keeps country-wide entries, since a visa rule for
    Egypt answers a Hurghada question. Entries found by meaning carry their similarity."""
    conditions = _filters(now, place_id, country, topics, fresh_only)
    by_words = await _by_words(db, query, conditions)
    similarity = await _by_meaning(db, query_vector, conditions)
    ids = fuse_rankings(list(similarity), by_words)[:limit]
    if not ids:
        return []
    rows = {
        row.id: row for row in (await db.execute(select(kb_entries).where(kb_entries.c.id.in_(ids)))).all()
    }
    return [_to_entry(rows[i], similarity.get(i)) for i in ids]


async def without_vectors(db: AsyncSession) -> list[tuple[int, str]]:
    """Entries with no vector, or a vector from another model, which is not comparable with ours."""
    stale = or_(kb_entries.c.embedding.is_(None), kb_entries.c.embedding_model.is_distinct_from(MODEL_NAME))
    query = select(kb_entries.c.id, kb_entries.c.text).where(stale)
    return [(row.id, row.text) for row in (await db.execute(query.order_by(kb_entries.c.id))).all()]


async def set_vectors(db: AsyncSession, vectors: dict[int, list[float]]) -> None:
    for entry_id, vector in vectors.items():
        await db.execute(
            update(kb_entries)
            .where(kb_entries.c.id == entry_id)
            .values(embedding=vector, embedding_model=MODEL_NAME)
        )
