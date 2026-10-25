"""Loads the committed knowledge base seed (Wikivoyage passages) on startup, once per seed version."""

import hashlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.facts import repository as facts_repository
from app.facts.model import Fact
from app.kb import repository
from app.kb.model import Entry

log = logging.getLogger(__name__)

SEED_PATH = Path(__file__).parent / "seed" / "wikivoyage.json"
VERSION_ENTITY = ("seed", "kb")


def seed_entries(path: Path = SEED_PATH) -> list[Entry]:
    rows = json.loads(path.read_text(encoding="utf-8"))["entries"]
    return [
        Entry(
            **{
                **row,
                "fetched_at": datetime.fromisoformat(row["fetched_at"]),
                "valid_until": datetime.fromisoformat(row["valid_until"]) if row.get("valid_until") else None,
                "created_by": "seed",
            }
        )
        for row in rows
    ]


async def load_kb_seed(sessionmaker: async_sessionmaker[AsyncSession], path: Path = SEED_PATH) -> bool:
    if not path.exists():
        log.warning("No knowledge base seed at %s", path)
        return False
    version = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    async with sessionmaker() as db:
        stored = await facts_repository.list_facts(db, *VERSION_ENTITY)
        if any(f.attribute == "version" and f.value == version for f in stored):
            return False
        entries = seed_entries(path)
        await repository.add_entries(db, entries)
        marker = Fact(
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
        await facts_repository.save_facts(db, [marker])
        await db.commit()
    log.info("Loaded knowledge base seed %s: %d entries", version, len(entries))
    return True
