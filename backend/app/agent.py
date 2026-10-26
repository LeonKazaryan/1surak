"""The agent loop: the model decides which tools to call, the code runs them and feeds results back.

One user turn looks like this:
    model → (text and/or tool calls) → run tools → model → … → final text
Every tool call is streamed to the UI as a tool_start / tool_end pair, so the user sees the agent work.
"""

import json
import logging
import re
from collections.abc import AsyncIterator, Callable
from datetime import datetime, timedelta, timezone

from app.llm import LLM, TextDelta, ToolCall, Usage
from app.money import RUB, Currency, current_currency
from app.tools import ToolRegistry

log = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 8
# Text this short followed by tool calls is the model thinking aloud, not the answer.
NARRATION_MAX_CHARS = 280
MSK = timezone(timedelta(hours=3), "MSK")  # Moscow has no DST, so a fixed offset is exact
WEEKDAYS_RU = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]

SYSTEM_PROMPT = """Тебя зовут 1surak, ты ИИ-агент для планирования поездок. \
Отвечай коротко и по делу, без длинных тире.

Язык: пиши на том же языке, что и последнее сообщение пользователя. На русское сообщение отвечай \
по-русски, на английское по-английски, даже если данные инструментов на русском.

Сегодня {today}, {weekday} (время московское).

Валюта пользователя: {currency}. Цены называй в ней, как в полях price и tickets_total: они уже \
пересчитаны. Сам не пересчитывай и рубли не пиши, если пользователь сам не спросил про рубли.

Что ты делаешь: помогаешь спланировать поездку, от идеи до покупки. На просьбы не о путешествиях \
(код, домашние задания, другие темы) вежливо откажись одной фразой и предложи помощь с поездкой.

Откуда брать факты:
- Цены, расписания, наличие мест, погоду и условия отелей бери только из результатов инструментов. \
Если инструмента для этого нет или он вернул ошибку, честно скажи об этом и не придумывай цифры.
- Если пользователь спрашивает о конкретном месте, открой его карточку (get_destination). \
Если места нет в каталоге, так и скажи, назови главную известную причину, почему туда сложно \
(например, для Франции и других стран Шенгена россиянам нужна шенгенская виза, прямых рейсов из России нет), \
без цифр и сроков, которых нет в инструментах, и предложи похожие места из каталога.
- Правила въезда и документы проверяй через research, даже если в карточке есть виза: \
в карточке только оценка команды. Через research же ищи события на даты, советы на месте \
(что делать, где поесть, какой район), транспорт (работает ли аэропорт, животные в поезде), безопасность \
и всё, чего нет в каталоге.
- Если пользователь дал ссылку, открой её через read_page, а не ищи заново.
- Если в ответе есть факты из research или read_page, закончи его строкой «Источники:» и списком: название, дата, ссылка.

Как вести диалог:
1. На каждое сообщение о поездке сначала вызови update_trip_brief. Передавай только сказанное явно \
или однозначно следующее из слов. Возраст, бюджет и число людей не придумывай.
2. Не устраивай анкету. Если missing не пуст и уточнений ещё не было, вызови ask_user один раз \
со всеми пунктами из missing: пользователь ответит на карточках. Вопросы о датах, составе и бюджете \
обычным текстом не задавай.
3. Иначе вызови search_destinations: возьми фильтры из search_hint и добавь то, что следует из пожеланий \
(«тёплое море» = море от 24 °C, «без долгих перелётов» = до 5 часов). Если совпадений мало, \
ослабь один фильтр и скажи об этом. Затем вызови show_destinations с 3-5 лучшими вариантами. \
Если отвечаешь с допущениями (assumptions), назови их в intro.
   Если в search_hint есть multi_city (пользователь хочет несколько городов: «по Европе», «по Кавказу»), \
вызови search_routes с теми же фильтрами и покажи 2-3 маршрута через show_destinations (поле route), \
одиночное место из search_destinations добавляй, только если маршрутов меньше двух. \
В маршруте может быть до 7 городов: «большой тур», «по 5 городам» = min_stops (и max_stops, если число \
названо). Если у плеча есть parts (поезд до соседнего города и прямой рейс вместо перелёта с пересадками), \
скажи об этом в intro одной фразой и назови экономию из instead. Семьям с маленькими детьми маршрут сам не предлагай.
   Если в search_hint есть also_routes (пользователь назвал страну, а не город: «хочу в Турцию», или хочет \
всего понемногу), покажи и то, и другое: 2-3 лучших города из search_destinations и 1-2 маршрута из \
search_routes с теми же countries и kinds (например, Анталья отдельно и Анталья + Стамбул + Каппадокия). Если маршрутов нет, \
покажи только города.
   Если пользователь хочет ехать поездом или автобусом («на поезде», «без самолётов», «боюсь летать»), \
передай by_land=true в update_trip_brief и в search_routes: плечи поедут поездом или автобусом везде, где они \
ходят (у плеча будет ground), самолёт останется только там, где их нет; такие плечи назови в intro.
   Если в search_hint есть route_places (пользователь сам перечислил города, и все они есть в каталоге: \
«Алматы и Самарканд»), вызови search_routes с places=route_places (order_fixed=true, только если порядок \
задан словами «сначала … потом …») и покажи этот маршрут через show_destinations (поле route): так у него \
будут ночи по городам, поезда и умные пересадки.
   Если в search_hint есть plan_route (пользователь сам перечислил города не из каталога: «Ташкент и Бишкек»), \
вызови plan_route с этими stops вместо search_routes (order_fixed=false, если порядок можно выбрать): маршрут появится карточкой \
с ценами и ссылками на покупку, ты коротко объясняешь выбор, пересадку через хаб (cheaper_via) и даты.
   Если пользователь назвал город вылета («из Алматы», «летим из Казани»), передай его в update_trip_brief \
(origin), даже если ниже в сообщении другой «Город вылета»: билеты \
дальше ищутся оттуда. Если вернулся origin_unknown, спроси текстом ближайший город с аэропортом.
   Если update_trip_brief вернул named_place (пользователь сам назвал место из каталога) и спрашивать \
нечего (missing пуст или уточнения уже были), не ищи и не показывай карточки: сразу собирай поездку \
по шагу 4 с этим id.
4. Когда пользователь выбрал направление или маршрут («Выбираю …») или назвал место, сразу вызови build_trip \
с id из named_place или shown_before (у маршрута id вида «tbilisi+yerevan»), затем show_trip. \
Не отвечай текстом вместо плана. Билеты на даты, отель под состав, \
трансферы, стыковки, программу по дням и бюджет собирает код, ты объясняешь результат.
   В intro пиши как живой турагент, который всё уже собрал: от первого лица, тепло и по делу, 2-3 предложения, \
без списков и заголовков. Даты, рейсы, цены и программа уже видны в плане: не пересказывай их. Скажи, почему \
этот отель подходит именно им, главное из проверок (warn), и чего из пожеланий найти не удалось (unmet, \
wishes_not_checked): прямо скажи «не нашёл» и предложи замену. Одной фразой скажи про отель: если real_hotel, он настоящий, а цена ориентировочная \
и условия уточним при бронировании; иначе отель демонстрационный.
5. Если план уже есть (current_plan) и пользователь меняет условие («на два дня позже», «бюджет меньше», \
«с нами собака», «другой отель»), не начинай поиск заново: обнови бриф через update_trip_brief, \
вызови build_trip с тем же id (другой отель: hotels с id из alternatives или названием, которое выбрал \
пользователь) и show_trip. Если просят показать другие отели («подешевле», «в центре», «ещё варианты»), \
сначала вызови search_hotels: варианты появятся карточками, пользователь выберет. \
В intro начни с того, что изменилось (changes).
- Перед вызовом инструментов текст не пиши: слова для пользователя передавай в intro."""

# Rules the model drops in long answers work when repeated right before it writes (like the language note).
# Only after tool results: on the first call it pushes the model to answer before looking anything up.
REPLY_CHECKLIST = (
    "Перед ответом проверь: 1) цифры и факты только из результатов инструментов; "
    "2) если использовал research или read_page, в конце блок «Источники:» со ссылками; "
    "3) даты, состав и бюджет уточняй только карточками ask_user и только один раз: если уточнение уже было, "
    "не спрашивай снова, а назови допущения; "
    "4) найденные через search_destinations места показывай вызовом show_destinations, не списком в тексте; "
    "5) выбранное место или маршрут собирай через build_trip и показывай через show_trip."
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


def system_prompt(now: datetime, currency: Currency = RUB) -> str:
    return SYSTEM_PROMPT.format(
        today=now.date().isoformat(),
        weekday=WEEKDAYS_RU[now.weekday()],
        currency=f"{currency.name} ({currency.sign})",
    )


# The city comes from the client, so it goes in the user turn: the system prompt must stay ours alone.
def _with_origin(turns: list[dict], origin: str | None) -> list[dict]:
    if not origin:
        return turns
    *earlier, last = turns
    note = f"Город вылета: {origin} (из настроек; если в сообщении назван другой город вылета, он главнее)"
    return [*earlier, {**last, "content": f"{last['content']}\n\n{note}"}]


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


def _tokens(chunks: list[str], after_text: bool) -> list[dict]:
    separator = (
        [{"type": "assistant_token", "text": "\n\n"}] if after_text else []
    )  # apart from earlier rounds
    return separator + [{"type": "assistant_token", "text": chunk} for chunk in chunks]


def _words(text: str) -> str:
    return " ".join(text.split())


def _repeats_an_argument(text: str, calls: list[ToolCall]) -> bool:
    """The model often says aloud the very intro it passes to a tool; the tool shows it anyway."""
    said = _words(text)
    return any(
        isinstance(value, str) and _words(value) == said
        for call in calls
        for value in _display_args(call.arguments).values()
    )


def _assistant_message(text: str, calls: list[ToolCall]) -> dict:
    return {
        "role": "assistant",
        "content": text or None,
        "tool_calls": [
            {"id": c.id, "type": "function", "function": {"name": c.name, "arguments": c.arguments or "{}"}}
            for c in calls
        ],
    }


class _Meter:
    """Adds up the tokens of every model call in one turn."""

    def __init__(self):
        self.calls = self.input = self.cached = self.output = 0

    def add(self, usage: Usage) -> None:
        self.calls += 1
        self.input += usage.input
        self.cached += usage.cached
        self.output += usage.output

    def event(self) -> dict:
        return {
            "type": "usage",
            "llm_calls": self.calls,
            "input_tokens": self.input,
            "cached_tokens": self.cached,
            "output_tokens": self.output,
        }


async def run(
    llm: LLM,
    turns: list[dict],
    tools: ToolRegistry | None = None,
    now: Callable[[], datetime] = now_msk,
    origin: str | None = None,
) -> AsyncIterator[dict]:
    """One agent turn. Ends with a `usage` event (tokens of the whole turn) when the model reports usage."""
    meter = _Meter()
    async for event in _run(llm, turns, tools, now, origin, meter):
        yield event
    if meter.calls:
        log.info(
            "turn: %d model calls, %d input tokens (%d cached), %d output",
            meter.calls, meter.input, meter.cached, meter.output,
        )  # fmt: skip
        yield meter.event()


async def _run(
    llm: LLM,
    turns: list[dict],
    tools: ToolRegistry | None,
    now: Callable[[], datetime],
    origin: str | None,
    meter: _Meter,
) -> AsyncIterator[dict]:
    tools = tools or ToolRegistry()
    specs = tools.specs() or None
    prompt = system_prompt(now(), current_currency.get())
    messages: list[dict] = [{"role": "system", "content": prompt}, *_with_origin(turns, origin)]
    language = _language_note(turns)
    checklist = [{"role": "system", "content": REPLY_CHECKLIST}]
    said_something = False
    owed: str | None = None  # a call the model still has to make before answering (Tool.then)
    force: str | None = None

    for round_index in range(MAX_TOOL_ROUNDS + 1):
        last_round = round_index == MAX_TOOL_ROUNDS
        if last_round:
            messages.append({"role": "system", "content": STEP_LIMIT_NOTE})

        text_parts: list[str] = []
        calls: list[ToolCall] = []
        # Short text is held back until we know whether tool calls follow it: then it is a step, not the answer.
        streaming = False
        async for event in llm.stream(
            [*messages, *(checklist if round_index else []), *language],
            None if last_round else specs,
            None if last_round else force,
        ):
            if isinstance(event, TextDelta):
                text_parts.append(event.text)
                if streaming:
                    yield {"type": "assistant_token", "text": event.text}
                elif sum(map(len, text_parts)) > NARRATION_MAX_CHARS:
                    streaming = True
                    for token in _tokens(text_parts, said_something):
                        yield token
            elif isinstance(event, ToolCall):
                calls.append(event)
            elif isinstance(event, Usage):
                meter.add(event)
        text = "".join(text_parts)
        force = None
        # The model answers in words while it still owes a call (found places, showed none): its words become
        # a step, and the next round makes the call. Once, so a refusing model cannot loop.
        insist = bool(owed) and not calls and not last_round
        if text.strip() and not streaming:
            if insist:
                yield {"type": "assistant_note", "text": text.strip()}
            elif not calls or last_round:
                streaming = True
                for token in _tokens(text_parts, said_something):
                    yield token
            elif not _repeats_an_argument(text, calls):
                yield {"type": "assistant_note", "text": text.strip()}
        said_something = said_something or streaming

        if insist:
            if text.strip():
                messages.append({"role": "assistant", "content": text})
            force, owed = owed, None
            continue
        if not calls or last_round:
            return

        messages.append(_assistant_message(text, calls))
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
            tool = tools.get(call.name)
            if call.name == owed:
                owed = None
            if result.ok and tool and tool.then and tools.get(tool.then):
                owed = tool.then
            # a long intro streams before the call that carries it; saying it again would double the reply
            if result.text and not (streaming and _words(result.text) == _words(text)):
                separator = "\n\n" if said_something else ""
                yield {"type": "assistant_token", "text": separator + result.text}
                said_something = True
            if result.event:
                yield result.event
            if result.ends_turn:
                return
