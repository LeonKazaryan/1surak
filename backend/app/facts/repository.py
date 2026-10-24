from dataclasses import asdict
from datetime import UTC, datetime

from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import facts
from app.facts.model import Fact, normalize


def _aware(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo:
        return value
    return value.replace(tzinfo=UTC)


def _same_period(period: str | None):
    return facts.c.period.is_(None) if period is None else facts.c.period == period


def _to_fact(row) -> Fact:
    return Fact(
        entity_type=row.entity_type,
        entity_id=row.entity_id,
        attribute=row.attribute,
        period=row.period,
        value=row.value,
        unit=row.unit,
        source=row.source,
        source_url=row.source_url,
        source_tier=row.source_tier,
        kind=row.kind,
        fetched_at=_aware(row.fetched_at),
        valid_until=_aware(row.valid_until),
    )


async def save_facts(db: AsyncSession, items: list[Fact]) -> None:
    latest = {(f.entity_type, f.entity_id, f.key, f.source): normalize(f) for f in items}
    for f in latest.values():
        await db.execute(
            delete(facts).where(
                facts.c.entity_type == f.entity_type,
                facts.c.entity_id == f.entity_id,
                facts.c.attribute == f.attribute,
                _same_period(f.period),
                facts.c.source == f.source,
            )
        )
    if latest:
        await db.execute(insert(facts), [asdict(f) for f in latest.values()])


async def list_facts(db: AsyncSession, entity_type: str, entity_id: str) -> list[Fact]:
    query = select(facts).where(facts.c.entity_type == entity_type, facts.c.entity_id == entity_id)
    return [_to_fact(row) for row in (await db.execute(query)).all()]
