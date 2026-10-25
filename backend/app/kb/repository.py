from datetime import UTC, datetime

from sqlalchemy import and_, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import kb_entries
from app.kb.model import Entry
from app.kb.text import fts_query


def _aware(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo:
        return value
    return value.replace(tzinfo=UTC)


def _to_entry(row) -> Entry:
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
    )


async def add_entries(db: AsyncSession, entries: list[Entry]) -> list[int]:
    """Writes new entries and indexes them. An exact duplicate (same text) keeps the stored one, but a
    re-fetch refreshes its dates, so a fact seen again today counts as fresh. Returns the ids."""
    ids: list[int] = []
    for entry in entries:
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
            )
        )
        entry_id = result.inserted_primary_key[0]
        await db.execute(
            text("INSERT INTO kb_fts(rowid, text) VALUES (:id, :text)"), {"id": entry_id, "text": entry.text}
        )
        ids.append(entry_id)
    return ids


async def search(
    db: AsyncSession,
    query: str,
    now: datetime,
    place_id: str | None = None,
    country: str | None = None,
    topics: list[str] | None = None,
    fresh_only: bool = True,
    limit: int = 6,
) -> list[Entry]:
    """Filter exactly (place or country, topic, status, freshness), then rank by full-text match (BM25).
    A place filter also keeps country-wide entries, since a visa rule for Egypt answers a Hurghada question."""
    match = fts_query(query)
    if match is None:
        return []
    ranked = (
        await db.execute(
            text(
                "SELECT rowid, bm25(kb_fts) AS rank FROM kb_fts WHERE kb_fts MATCH :q ORDER BY rank LIMIT 200"
            ),
            {"q": match},
        )
    ).all()
    if not ranked:
        return []
    order = {row.rowid: i for i, row in enumerate(ranked)}

    conditions = [kb_entries.c.id.in_(list(order)), kb_entries.c.status == "active"]
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
    rows = (await db.execute(select(kb_entries).where(*conditions))).all()
    return sorted((_to_entry(r) for r in rows), key=lambda e: order[e.id])[:limit]


async def count(db: AsyncSession) -> int:
    return (await db.execute(text("SELECT count(*) FROM kb_entries"))).scalar_one()
