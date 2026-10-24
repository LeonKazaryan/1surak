import logging
from collections.abc import AsyncIterator

import anyio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app import agent
from app.chats import repository
from app.llm import LLM

log = logging.getLogger(__name__)

TITLE_MAX_CHARS = 60
HISTORY_TURNS = 40
AGENT_ERROR_MESSAGE = "Не получилось получить ответ. Попробуйте ещё раз чуть позже."
INTERRUPTED_MESSAGE = "Ответ прерван."


def title_from(query: str) -> str:
    return query if len(query) <= TITLE_MAX_CHARS else f"{query[: TITLE_MAX_CHARS - 1]}…"


def _final_answer(parts: list[str], failed: bool, finished: bool) -> str:
    if parts:
        return "".join(parts)
    if failed:
        return AGENT_ERROR_MESSAGE
    return "" if finished else INTERRUPTED_MESSAGE


async def stream_reply(
    sessionmaker: async_sessionmaker[AsyncSession],
    llm: LLM,
    chat_id: str,
    query: str,
    origin: str | None = None,
) -> AsyncIterator[dict]:
    # Sessions are opened here, not injected: the stream outlives the request handler.
    async with sessionmaker() as db:
        title = await repository.ensure_chat(db, chat_id, title_from(query))
        history = await repository.recent_turns(db, chat_id, HISTORY_TURNS)
        await repository.add_message(db, chat_id, "user", query)
        await db.commit()

    answer_parts: list[str] = []
    trace: list[dict] = []
    failed = finished = False
    try:
        async for event in agent.run(llm, [*history, {"role": "user", "content": query}], origin):
            if event["type"] == "assistant_token":
                answer_parts.append(event["text"])
            else:
                trace.append(event)
            yield event
        finished = True
    except Exception:
        log.exception("Agent failed for chat %s", chat_id)
        failed = True
        error = {"type": "error", "message": AGENT_ERROR_MESSAGE}
        trace.append(error)
        yield error
    finally:
        answer = _final_answer(answer_parts, failed, finished)
        # Starlette cancels the stream when the client disconnects; the shield lets the reply still be saved.
        with anyio.CancelScope(shield=True):
            async with sessionmaker() as db:
                await repository.add_message(db, chat_id, "assistant", answer, trace)
                await db.commit()
    yield {"type": "done", "answer": answer, "chat_id": chat_id, "title": title}
