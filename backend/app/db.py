from pathlib import Path

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Index, Integer, MetaData, Table, Text, func
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine

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
# The integer id is what the agent cites («kb:42») and also the rowid of the full-text index below.
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
)

KB_FTS_DDL = (
    "CREATE VIRTUAL TABLE IF NOT EXISTS kb_fts USING fts5(text, tokenize='unicode61 remove_diacritics 2')"
)


async def init_db(engine: AsyncEngine) -> None:
    url = make_url(str(engine.url))
    if url.get_backend_name() == "sqlite" and url.database:
        Path(url.database).parent.mkdir(parents=True, exist_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
        if url.get_backend_name() == "sqlite":
            await conn.exec_driver_sql(KB_FTS_DDL)
