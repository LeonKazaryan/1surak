import asyncio
from uuid import uuid4

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.chats import repository, service
from app.db import init_db
from tests.conftest import FakeLLM


async def _reply_closed_after(db_url: str, stop_after: str) -> list[dict]:
    engine = create_async_engine(db_url)
    await init_db(engine)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    chat_id = str(uuid4())

    stream = service.stream_reply(
        sessionmaker, FakeLLM(chunks=["Част", "ично", " и ещё"]), chat_id, "Хочу к морю"
    )
    async for event in stream:
        if event.get("text") == stop_after or event["type"] == stop_after:
            break
    await stream.aclose()

    async with sessionmaker() as db:
        messages = await repository.list_messages(db, chat_id)
    await engine.dispose()
    return messages


def test_should_save_the_partial_reply_when_the_client_disconnects(tmp_path):
    messages = asyncio.run(_reply_closed_after(f"sqlite+aiosqlite:///{tmp_path / 'chat.db'}", "ично"))

    assert [(m["role"], m["content"]) for m in messages] == [
        ("user", "Хочу к морю"),
        ("assistant", "Частично"),
    ]


def test_should_mark_the_reply_interrupted_when_the_client_leaves_before_any_text(tmp_path):
    messages = asyncio.run(_reply_closed_after(f"sqlite+aiosqlite:///{tmp_path / 'chat.db'}", "tool_start"))

    assert [(m["role"], m["content"]) for m in messages] == [
        ("user", "Хочу к морю"),
        ("assistant", service.INTERRUPTED_MESSAGE),
    ]
