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


async def init_db(engine: AsyncEngine) -> None:
    url = make_url(str(engine.url))
    if url.get_backend_name() == "sqlite" and url.database:
        Path(url.database).parent.mkdir(parents=True, exist_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
