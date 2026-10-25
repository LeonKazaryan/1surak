"""Loads the committed catalogue facts into the database on startup, once per seed version."""

import hashlib
import logging
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.catalog.catalog import (
    CURATED_PATH,
    GEO_PATH,
    SEED_FACTS_PATH,
    curated_facts,
    load_catalog,
    seed_facts,
)
from app.facts import repository
from app.facts.model import Fact

log = logging.getLogger(__name__)

VERSION_ENTITY = ("seed", "catalog")


def seed_version() -> str:
    digest = hashlib.sha256()
    for path in (CURATED_PATH, GEO_PATH, SEED_FACTS_PATH):
        digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


def _version_fact(version: str) -> Fact:
    return Fact(
        entity_type=VERSION_ENTITY[0],
        entity_id=VERSION_ENTITY[1],
        attribute="version",
        value=version,
        unit=None,
        source="1surak-seed",
        source_tier="community",
        kind="synthetic",
        fetched_at=datetime.now(UTC),
    )


async def _loaded_version(db: AsyncSession) -> str | None:
    for fact in await repository.list_facts(db, *VERSION_ENTITY):
        if fact.attribute == "version":
            return fact.value
    return None


async def load_catalog_facts(sessionmaker: async_sessionmaker[AsyncSession]) -> bool:
    """Returns True when facts were (re)loaded, False when the database already had this version."""
    version = seed_version()
    async with sessionmaker() as db:
        if await _loaded_version(db) == version:
            return False
        items = curated_facts(load_catalog()) + seed_facts()
        await repository.save_facts(db, [*items, _version_fact(version)])
        await db.commit()
    log.info("Loaded catalogue seed %s: %d facts", version, len(items))
    return True
