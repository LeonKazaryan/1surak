from pathlib import Path

from sqlalchemy import JSON, Column, DateTime, ForeignKey, MetaData, Table, Text
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


async def init_db(engine: AsyncEngine) -> None:
    url = make_url(str(engine.url))
    if url.get_backend_name() == "sqlite" and url.database:
        Path(url.database).parent.mkdir(parents=True, exist_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
