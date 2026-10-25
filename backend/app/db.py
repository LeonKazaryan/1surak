import re

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Column,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Table,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.kb.embeddings import DIMENSIONS

metadata = MetaData()

chats = Table(
    "chats",
    metadata,
    Column("id", Text, primary_key=True),
    Column("title", Text),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

chat_messages = Table(
    "chat_messages",
    metadata,
    Column("id", Text, primary_key=True),
    Column("chat_id", Text, ForeignKey("chats.id"), nullable=False, index=True),
    Column("role", Text, nullable=False),
    Column("content", Text, nullable=False),
    Column("trace", JSON, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

# What the agent knows about the chat's trip (app.trip.TripBrief), carried from turn to turn.
trip_briefs = Table(
    "trip_briefs",
    metadata,
    Column("chat_id", Text, ForeignKey("chats.id"), primary_key=True),
    Column("brief", JSON, nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)


facts = Table(
    "facts",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("entity_type", Text, nullable=False),
    Column("entity_id", Text, nullable=False),
    Column("attribute", Text, nullable=False),
    Column("period", Text),
    Column("value", JSON, nullable=False),
    Column("unit", Text),
    Column("source", Text, nullable=False),
    Column("source_url", Text),
    Column("source_tier", Text, nullable=False),
    Column("kind", Text, nullable=False),
    Column("fetched_at", DateTime(timezone=True), nullable=False),
    Column("valid_until", DateTime(timezone=True)),
)

# coalesce, because a unique index treats every NULL period as distinct
Index(
    "ux_facts_source_value",
    facts.c.entity_type,
    facts.c.entity_id,
    facts.c.attribute,
    func.coalesce(facts.c.period, ""),
    facts.c.source,
    unique=True,
)


# Cached Aviasales prices per city pair and month (app/flights/fares.py), so they survive a restart.
# price_rub NULL means Aviasales had no tickets: also worth remembering, until it expires.
fares = Table(
    "fares",
    metadata,
    Column("origin", Text, primary_key=True),  # city code: MOW, never SVO
    Column("destination", Text, primary_key=True),
    Column("month", Text, primary_key=True),  # "2026-11", or "" for the nearest dates
    Column("price_rub", Integer),
    Column("direct_price_rub", Integer),
    Column("duration_min", Integer),
    Column("tickets", JSON, nullable=False),  # {"cheapest": {...}, "direct": {...} | null, "fastest": {...}}
    Column("source", Text, nullable=False),
    Column("fetched_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False, index=True),
)


# The knowledge base the agent keeps growing with web search (docs/09-living-knowledge-base.md).
# The integer id is what the agent cites («kb:42»).
kb_entries = Table(
    "kb_entries",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("text", Text, nullable=False),
    Column("topic", Text, nullable=False),
    Column("kind", Text, nullable=False),
    Column("place_id", Text, index=True),
    Column("country", Text, index=True),
    Column("entities", JSON, nullable=False),
    Column("attributes", JSON, nullable=False),
    Column("source_url", Text, nullable=False),
    Column("source_title", Text),
    Column("source_tier", Text, nullable=False),
    Column("confidence", Text, nullable=False),
    Column("lang", Text, nullable=False),
    Column("published_at", Text),
    Column("fetched_at", DateTime(timezone=True), nullable=False),
    Column("valid_until", DateTime(timezone=True)),
    Column("content_hash", Text, nullable=False, unique=True),
    Column("created_by", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("query", Text),
    # 'simple' keeps every word form; kb.text cuts Russian endings and searches by prefix instead
    Column(
        "search", TSVECTOR, Computed("to_tsvector('simple', replace(lower(text), 'ё', 'е'))", persisted=True)
    ),
    Column("embedding", Vector(DIMENSIONS)),
    Column("embedding_model", Text),
)
Index("ix_kb_entries_search", kb_entries.c.search, postgresql_using="gin")

DISPOSABLE_DATABASE = re.compile(
    r"[a-z0-9_]+_(test(_[a-z0-9]+)?|eval)"
)  # fullmatch, so the name is also safe to quote


async def init_db(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(metadata.create_all)


async def ensure_database(url: str) -> None:
    target = make_url(url)
    admin = create_async_engine(target.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        async with admin.connect() as conn:
            found = await conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": target.database}
            )
            if not found:
                await conn.execute(text(f'CREATE DATABASE "{target.database}"'))
    finally:
        await admin.dispose()


async def reset_database(url: str) -> None:
    """Creates the database if needed and empties every table. Only for *_test and *_eval databases."""
    name = make_url(url).database or ""
    if not DISPOSABLE_DATABASE.fullmatch(name):
        raise ValueError(f"refusing to empty {name!r}: only *_test and *_eval databases can be reset")
    await ensure_database(url)
    engine = create_async_engine(url)
    try:
        await init_db(engine)
        tables = ", ".join(table.name for table in metadata.sorted_tables)
        async with engine.begin() as conn:
            await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    finally:
        await engine.dispose()
