import asyncio
from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db import facts, init_db
from app.facts import repository, service
from app.facts.model import Fact

NOW = datetime(2026, 10, 25, 12, tzinfo=UTC)


def fact(value, **overrides) -> Fact:
    base = {
        "entity_type": "place",
        "entity_id": "Q1",
        "attribute": "sea_temp",
        "period": "m11",
        "value": value,
        "unit": "°C",
        "source": "copernicus",
        "source_tier": "official",
        "kind": "real",
        "fetched_at": NOW - timedelta(days=1),
    }
    return Fact(**{**base, **overrides})


async def _with_db(db_url: str, work):
    engine = create_async_engine(db_url)
    await init_db(engine)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            return await work(db)
    finally:
        await engine.dispose()


def test_should_keep_one_value_per_source_and_replace_it_on_refetch(db_url):
    async def work(db):
        await repository.save_facts(db, [fact(25.0, source="a"), fact(24.0, source="b")])
        await repository.save_facts(db, [fact(26.0, source="a", fetched_at=NOW)])
        await db.commit()
        return await repository.list_facts(db, "place", "Q1")

    stored = asyncio.run(_with_db(db_url, work))

    assert sorted((f.source, f.value) for f in stored) == [("a", 26.0), ("b", 24.0)]


def test_should_store_facts_in_canonical_units(db_url):
    async def work(db):
        await repository.save_facts(db, [fact(77.0, unit="°F")])
        await db.commit()
        return await repository.list_facts(db, "place", "Q1")

    stored = asyncio.run(_with_db(db_url, work))

    assert [(f.value, f.unit) for f in stored] == [(25.0, "°C")]


def test_should_resolve_each_attribute_and_period_of_a_place_separately(db_url):
    async def work(db):
        await repository.save_facts(
            db,
            [
                fact(26.0, source="a"),
                fact(21.0, source="b", source_tier="media"),
                fact(22.0, period="m12"),
                fact(30.0, attribute="air_max", period="m11"),
                fact(15.0, entity_id="Q2"),
            ],
        )
        await db.commit()
        return await service.resolve_entity(db, "place", "Q1", NOW)

    resolved = asyncio.run(_with_db(db_url, work))

    assert {key: r.chosen.value for key, r in resolved.items()} == {
        ("sea_temp", "m11"): 26.0,
        ("sea_temp", "m12"): 22.0,
        ("air_max", "m11"): 30.0,
    }
    assert resolved[("sea_temp", "m11")].conflict
    assert not resolved[("sea_temp", "m12")].conflict


def test_should_read_back_the_same_moment_that_was_saved_with_an_offset(db_url):
    moscow_noon = datetime(2026, 10, 25, 12, tzinfo=timezone(timedelta(hours=3)))

    async def work(db):
        await repository.save_facts(db, [fact(25.0, fetched_at=moscow_noon, valid_until=moscow_noon)])
        await db.commit()
        return await repository.list_facts(db, "place", "Q1")

    [stored] = asyncio.run(_with_db(db_url, work))

    assert (stored.fetched_at, stored.valid_until) == (moscow_noon, moscow_noon)


def test_should_refuse_a_second_row_for_the_same_source_and_fact(db_url):
    row = {
        "entity_type": "place",
        "entity_id": "Q1",
        "attribute": "visa_rule",
        "period": None,
        "value": "visa_free",
        "source": "mfa",
        "source_tier": "official",
        "kind": "real",
        "fetched_at": NOW,
    }

    async def work(db):
        await db.execute(insert(facts), [row])
        await db.execute(insert(facts), [row])

    with pytest.raises(IntegrityError):
        asyncio.run(_with_db(db_url, work))
