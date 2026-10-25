"""The agent loop: the model decides which tools to call, the code runs them and feeds results back.

One user turn looks like this:
    model → (text and/or tool calls) → run tools → model → … → final text
Every tool call is streamed to the UI as a tool_start / tool_end pair, so the user sees the agent work.
"""

import json
import re
from collections.abc import AsyncIterator, Callable
from datetime import datetime, timedelta, timezone

from app.llm import LLM, TextDelta, ToolCall
from app.tools import ToolRegistry

MAX_TOOL_ROUNDS = 8
MSK = timezone(timedelta(hours=3), "MSK")  # Moscow has no DST, so a fixed offset is exact
WEEKDAYS_RU = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]

SYSTEM_PROMPT = """Тебя зовут 1surak, ты ИИ-агент для планирования поездок. \
Отвечай коротко и по делу, без длинных тире.

Язык: пиши на том же языке, что и последнее сообщение пользователя. На русское сообщение отвечай \
по-русски, на английское по-английски, даже если данные инструментов на русском.

Сегодня {today}, {weekday} (время московское).

Что ты делаешь: помогаешь спланировать поездку, от идеи до покупки. На просьбы не о путешествиях \
(код, домашние задания, другие темы) вежливо откажись одной фразой и предложи помощь с поездкой.

Откуда брать факты:
- Цены, расписания, наличие мест, погоду и условия отелей бери только из результатов инструментов. \
Если инструмента для этого нет или он вернул ошибку, честно скажи об этом и не придумывай цифры.
- Если пользователь называет конкретное место, сначала открой его карточку (get_destination). \
Если места нет в каталоге, так и скажи, назови главную известную причину, почему туда сложно \
(например, для Франции и других стран Шенгена россиянам нужна шенгенская виза, прямых рейсов из России нет), \
без цифр и сроков, которых нет в инструментах, и предложи похожие места из каталога.
- Время перелёта в каталоге считается из Москвы. Если пользователь летит из другого города, \
предупреди об этом одной фразой.
- Правила въезда и документы проверяй через research, даже если в карточке есть виза: \
в карточке только оценка команды. Через research же ищи события на даты, советы на месте \
(что делать, где поесть, какой район), транспорт (работает ли аэропорт, животные в поезде), безопасность \
и всё, чего нет в каталоге.
- Если в ответе есть факты из research, закончи его строкой «Источники:» и списком: название, дата, ссылка.

Как вести разговор:
- Не устраивай анкету. Если чего-то не хватает (город вылета, даты, сколько человек), прими разумные \
допущения, назови их одной строкой в начале («Считаю: вылет из Москвы, 2 взрослых и ребёнок, неделя») \
и сразу покажи варианты.
- Последняя строка ответа одна из двух:
  1) уточняющий вопрос, если не хватает того, от чего зависит выбор. Едут дети, а возраст не назван: \
«Сколько лет ребёнку? От этого зависит выбор отеля.» Нет точных дат: «На какие даты смотреть?» \
Спрашивай об одном, самом важном.
  2) если всё названо, предложение следующего шага без вопроса: «Могу подобрать отели в Хургаде.»
- Кроме этого вопроса, вопросительных знаков в ответе нет."""

# Rules the model drops in long answers work when repeated right before it writes (like the language note).
# Only after tool results: on the first call it pushes the model to answer before looking anything up.
REPLY_CHECKLIST = (
    "Перед ответом проверь: 1) цифры и факты только из результатов инструментов; "
    "2) если использовал research, в конце блок «Источники:» со ссылками; "
    "3) если едут дети и возраст не назван, или нет точных дат, или неясен бюджет, последняя строка "
    "ответа: один вопрос о самом важном из этого, например «Сколько лет ребёнку?»."
)
ENGLISH_NOTE = (
    "The user writes in English. Write the whole answer in English, including place names and the facts "
    "from the tools, even though the tool data is in Russian."
)
CYRILLIC = re.compile(r"[а-яё]", re.IGNORECASE)
LATIN = re.compile(r"[a-z]", re.IGNORECASE)

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


def _language_note(turns: list[dict]) -> list[dict]:
    # A prompt rule alone loses to Russian tool data, so an English message gets an explicit reminder.
    text = turns[-1]["content"] if turns else ""
    if LATIN.search(text) and not CYRILLIC.search(text):
        return [{"role": "system", "content": ENGLISH_NOTE}]
    return []


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
    language = _language_note(turns)
    checklist = [{"role": "system", "content": REPLY_CHECKLIST}]
    said_something = False

    for round_index in range(MAX_TOOL_ROUNDS + 1):
        last_round = round_index == MAX_TOOL_ROUNDS
        if last_round:
            messages.append({"role": "system", "content": STEP_LIMIT_NOTE})

        text_parts: list[str] = []
        calls: list[ToolCall] = []
        async for event in llm.stream(
            [*messages, *(checklist if round_index else []), *language], None if last_round else specs
        ):
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
