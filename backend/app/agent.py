"""The agent loop: the model decides which tools to call, the code runs them and feeds results back.

One user turn looks like this:
    model → (text and/or tool calls) → run tools → model → … → final text
Every tool call is streamed to the UI as a tool_start / tool_end pair, so the user sees the agent work.
"""

import json
from collections.abc import AsyncIterator, Callable
from datetime import datetime, timedelta, timezone

from app.llm import LLM, TextDelta, ToolCall
from app.tools import ToolRegistry

MAX_TOOL_ROUNDS = 8
MSK = timezone(timedelta(hours=3), "MSK")  # Moscow has no DST, so a fixed offset is exact
WEEKDAYS_RU = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]

SYSTEM_PROMPT = """Тебя зовут 1surak, ты ИИ-агент для планирования поездок. \
Отвечай по-русски, коротко и по делу, без длинных тире.

Сегодня {today}, {weekday} (время московское).

Правила:
- Цены, расписания, наличие мест, погоду и условия отелей бери только из результатов инструментов. \
Если инструмента для этого нет или он вернул ошибку, честно скажи об этом и не придумывай цифры.
- Если для следующего шага не хватает данных, сначала вызови подходящий инструмент.
- Уточняй у пользователя только то, без чего нельзя двигаться дальше, и не больше одного вопроса за раз."""

STEP_LIMIT_NOTE = "Лимит вызовов инструментов на этот ответ исчерпан. Ответь пользователю, опираясь на уже полученные данные."


def now_msk() -> datetime:
    return datetime.now(MSK)


def system_prompt(now: datetime) -> str:
    return SYSTEM_PROMPT.format(today=now.date().isoformat(), weekday=WEEKDAYS_RU[now.weekday()])


# The city comes from the client, so it goes in the user turn: the system prompt must stay ours alone.
def _with_origin(turns: list[dict], origin: str | None) -> list[dict]:
    if not origin:
        return turns
    *earlier, last = turns
    return [*earlier, {**last, "content": f"{last['content']}\n\nГород вылета: {origin}"}]


def _display_args(raw: str) -> dict:
    try:
        args = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    return args if isinstance(args, dict) else {}


def _assistant_message(text: str, calls: list[ToolCall]) -> dict:
    return {
        "role": "assistant",
        "content": text or None,
        "tool_calls": [
            {"id": c.id, "type": "function", "function": {"name": c.name, "arguments": c.arguments or "{}"}}
            for c in calls
        ],
    }


async def run(
    llm: LLM,
    turns: list[dict],
    tools: ToolRegistry | None = None,
    now: Callable[[], datetime] = now_msk,
    origin: str | None = None,
) -> AsyncIterator[dict]:
    tools = tools or ToolRegistry()
    specs = tools.specs() or None
    messages: list[dict] = [{"role": "system", "content": system_prompt(now())}, *_with_origin(turns, origin)]
    said_something = False

    for round_index in range(MAX_TOOL_ROUNDS + 1):
        last_round = round_index == MAX_TOOL_ROUNDS
        if last_round:
            messages.append({"role": "system", "content": STEP_LIMIT_NOTE})

        text_parts: list[str] = []
        calls: list[ToolCall] = []
        async for event in llm.stream(messages, None if last_round else specs):
            if isinstance(event, TextDelta):
                if not text_parts and said_something:
                    yield {"type": "assistant_token", "text": "\n\n"}  # separate text from earlier rounds
                text_parts.append(event.text)
                yield {"type": "assistant_token", "text": event.text}
            elif isinstance(event, ToolCall):
                calls.append(event)
        said_something = said_something or bool(text_parts)

        if not calls or last_round:
            return

        messages.append(_assistant_message("".join(text_parts), calls))
        for call in calls:
            yield {
                "type": "tool_start",
                "name": call.name,
                "title": tools.title(call.name),
                "args": _display_args(call.arguments),
            }
            result = await tools.execute(call.name, call.arguments)
            yield {"type": "tool_end", "name": call.name, "output_preview": result.preview, "ok": result.ok}
            messages.append({"role": "tool", "tool_call_id": call.id, "content": result.content})
