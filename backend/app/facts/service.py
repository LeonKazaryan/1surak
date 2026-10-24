from collections import defaultdict
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.facts import repository
from app.facts.model import Fact
from app.facts.resolve import Resolution, resolve


async def resolve_entity(
    db: AsyncSession, entity_type: str, entity_id: str, now: datetime
) -> dict[tuple[str, str | None], Resolution]:
    grouped: dict[tuple[str, str | None], list[Fact]] = defaultdict(list)
    for fact in await repository.list_facts(db, entity_type, entity_id):
        grouped[fact.key].append(fact)
    return {key: resolution for key, group in grouped.items() if (resolution := resolve(group, now))}
