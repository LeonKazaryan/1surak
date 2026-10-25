from collections import defaultdict
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.facts import repository
from app.facts.model import Fact
from app.facts.resolve import Resolution, resolve

Resolved = dict[tuple[str, str | None], Resolution]


def _resolve_all(items: list[Fact], now: datetime) -> Resolved:
    grouped: dict[tuple[str, str | None], list[Fact]] = defaultdict(list)
    for fact in items:
        grouped[fact.key].append(fact)
    return {key: resolution for key, group in grouped.items() if (resolution := resolve(group, now))}


async def resolve_entity(db: AsyncSession, entity_type: str, entity_id: str, now: datetime) -> Resolved:
    return _resolve_all(await repository.list_facts(db, entity_type, entity_id), now)


async def resolve_entities(
    db: AsyncSession, entity_type: str, entity_ids: list[str], now: datetime
) -> dict[str, Resolved]:
    """One query for many entities; entities without facts map to an empty dict."""
    by_entity: dict[str, list[Fact]] = defaultdict(list)
    for fact in await repository.list_facts_many(db, entity_type, entity_ids):
        by_entity[fact.entity_id].append(fact)
    return {entity_id: _resolve_all(by_entity.get(entity_id, []), now) for entity_id in entity_ids}
