import asyncio

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from app.db import init_db, reset_database


async def _extensions(db_url: str) -> set[str]:
    engine = create_async_engine(db_url)
    try:
        await init_db(engine)
        async with engine.connect() as conn:
            return set((await conn.scalars(text("SELECT extname FROM pg_extension"))).all())
    finally:
        await engine.dispose()


def test_should_enable_pgvector_when_the_database_starts(db_url):
    assert "vector" in asyncio.run(_extensions(db_url))


@pytest.mark.parametrize(
    "name",
    ["onesurak", "production", "onesurak_tests_backup", 'x"; DROP DATABASE victim; --_test', "prod_test\n"],
)
def test_should_refuse_to_empty_a_database_that_is_not_a_test_or_eval_one(name):
    with pytest.raises(ValueError):
        asyncio.run(
            reset_database(str(make_url("postgresql+asyncpg://u:p@127.0.0.1:1/x").set(database=name)))
        )
