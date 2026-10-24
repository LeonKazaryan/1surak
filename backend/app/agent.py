from collections.abc import AsyncIterator

from app.llm import LLM

SYSTEM_PROMPT = (
    "Тебя зовут 1surak, ты ИИ-агент для планирования поездок. Отвечай по-русски, коротко и по делу, без длинных тире. "
    "У тебя пока нет доступа к ценам, рейсам и наличию мест: не придумывай их, а честно скажи об этом."
)

REPLY_STEP = {"name": "compose_reply", "title": "Обдумываю ответ"}


# The city comes from the client, so it goes in the user turn: the system prompt must stay ours alone.
def _with_origin(turns: list[dict], origin: str | None) -> list[dict]:
    if not origin:
        return turns
    *earlier, last = turns
    return [*earlier, {**last, "content": f"{last['content']}\n\nГород вылета: {origin}"}]


async def run(llm: LLM, turns: list[dict], origin: str | None = None) -> AsyncIterator[dict]:
    yield {"type": "tool_start", **REPLY_STEP}
    try:
        async for text in llm.stream(
            [{"role": "system", "content": SYSTEM_PROMPT}, *_with_origin(turns, origin)]
        ):
            yield {"type": "assistant_token", "text": text}
    except Exception:
        yield {"type": "tool_end", "name": REPLY_STEP["name"], "output_preview": "Не удалось ответить"}
        raise
    yield {"type": "tool_end", "name": REPLY_STEP["name"], "output_preview": "Ответ готов"}
