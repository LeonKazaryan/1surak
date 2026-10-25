import asyncio
from uuid import uuid4

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.chats import repository, service
from app.db import init_db
from app.llm import ToolCall
from tests.conftest import FakeLLM


async def _reply_closed_after(db_url: str, stop_after: str, llm: FakeLLM | None = None) -> list[dict]:
    engine = create_async_engine(db_url)
    await init_db(engine)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    chat_id = str(uuid4())

    llm = llm or FakeLLM(chunks=["Част", "ично", " и ещё"])
    stream = service.stream_reply(sessionmaker, llm, chat_id, "Хочу к морю")
    async for event in stream:
        if event.get("text") == stop_after or event["type"] == stop_after:
            break
    await stream.aclose()

    async with sessionmaker() as db:
        messages = await repository.list_messages(db, chat_id)
    await engine.dispose()
    return messages


def test_should_save_the_partial_reply_when_the_client_disconnects(db_url):
    messages = asyncio.run(_reply_closed_after(db_url, "ично"))

    assert [(m["role"], m["content"]) for m in messages] == [
        ("user", "Хочу к морю"),
        ("assistant", "Частично"),
    ]


def test_should_mark_the_reply_interrupted_when_the_client_leaves_before_any_text(db_url):
    llm = FakeLLM(rounds=[[ToolCall(id="c1", name="search", arguments="{}")], ["Нашёл"]])
    messages = asyncio.run(_reply_closed_after(db_url, "tool_start", llm))

    assert [(m["role"], m["content"]) for m in messages] == [
        ("user", "Хочу к морю"),
        ("assistant", service.INTERRUPTED_MESSAGE),
    ]
