"""Scores one finished conversation against its case. Pure functions, so they're unit-tested without a model."""

import json
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from itertools import pairwise

# «26 °C», «26°», «26 градусов», «5 ч», «5,5 часа», «9.5 h», «-3 °C»
# (?<![\d.,]) keeps the dash of a range («23,5-23,7 °C») from reading as a minus
TEMPERATURE = re.compile(r"(?<![\d.,])(-?\d+(?:[.,]\d+)?)\s*(?:°|градус)", re.IGNORECASE)
SOURCE = re.compile(
    r"https?://|\b[\w-]+\.(?:ru|com|org|net|ae|th|cn|tr|eg|gov|travel|info|io)\b|Wikivoyage", re.IGNORECASE
)
HOURS = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:ч\b|час|h\b|hour)", re.IGNORECASE)
GROUNDING_TOLERANCE = 1.0
# What puts a recommendation on screen: destination cards, a route, the whole trip, more hotels.
RECOMMENDATIONS = {"destinations", "flight_plan", "trip_plan", "hotel_options"}
NIGHT_ENDS = (
    "06:00"  # land before it and the night before is booked; leave before it and the last night is paid
)


@dataclass
class ToolCallRecord:
    name: str
    args: dict
    ok: bool
    content: str  # the raw result the model saw


@dataclass
class Transcript:
    replies: list[str] = field(default_factory=list)
    calls: list[ToolCallRecord] = field(default_factory=list)
    first_token_s: list[float] = field(default_factory=list)  # per turn, None if no text came
    total_s: float = 0.0
    error: str | None = None
    llm_calls: int = 0
    input_tokens: int = 0
    cached_tokens: int = 0
    output_tokens: int = 0
    clarify_questions: int = 0  # fields on the clarifying cards
    asked_rounds: int | None = None  # replies that asked something: a card or a question in the text
    first_step_s: float | None = None  # until the first step of the agent's work was on screen
    first_pick_s: float | None = None  # until the first recommendation was on screen
    shown: list[str] = field(default_factory=list)  # names on the cards, the route and the plan
    plans: list[dict] = field(default_factory=list)  # every trip plan shown, as the screen got it


def research_sources(calls: list[ToolCallRecord]) -> list[str]:
    """Where each research call got its answer: «база знаний», «интернет» or a fallback."""
    found = []
    for call in calls:
        if call.name == "research" and call.ok:
            try:
                found.append(json.loads(call.content).get("answered_from", "?"))
            except json.JSONDecodeError:
                found.append("?")
    return found


@dataclass
class Score:
    case_id: str
    category: str
    failures: list[str]
    questions: int
    ungrounded: list[str]
    tools: list[str]
    first_token_s: float | None
    total_s: float
    research_from: list[str] = field(default_factory=list)
    llm_calls: int = 0
    input_tokens: int = 0
    cached_tokens: int = 0
    output_tokens: int = 0
    first_pick_s: float | None = None
    first_step_s: float | None = None
    card_fields: int = 0
    plans: int = 0
    legs_checked: int = 0
    stitch_errors: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.failures


def count_questions(text: str) -> int:
    # one question per sentence, however many «?» it ends with; a «?» inside a link is not a question
    return len(re.findall(r"\?+", re.sub(r"https?://\S+", "", text)))


def _to_float(raw: str) -> float:
    return float(raw.replace(",", "."))


def ungrounded_numbers(answer: str, calls: list[ToolCallRecord], user_text: str = "") -> list[str]:
    """Temperatures and hours in the answer that neither a tool result nor the user gave (within ±1)."""
    sources = [call.content for call in calls] + [user_text]
    known = [_to_float(n) for text in sources for n in re.findall(r"-?\d+(?:[.,]\d+)?", text)]
    claims = [
        (m.group(0), _to_float(m.group(1)))
        for pattern in (TEMPERATURE, HOURS)
        for m in pattern.finditer(answer)
    ]
    return [text for text, value in claims if not any(abs(value - k) <= GROUNDING_TOLERANCE for k in known)]


def _next_day(iso: str) -> str:
    return (date.fromisoformat(iso) + timedelta(days=1)).isoformat()


def stitching_errors(plan: dict) -> tuple[list[str], int]:
    """What a trip plan must never have: a night without a bed or paid twice, a flight that leaves before the
    previous one lands, a landing or a take-off that misses the hotel nights. Times are local to the city they
    happen in, so a landing and the next take-off from the same city compare. Returns the errors and the number
    of timed legs checked."""
    errors: list[str] = []
    stops = plan.get("stops") or []
    for stop in stops:
        if stop["check_in"] >= stop["check_out"]:
            errors.append(f"{stop['name']}: ни одной ночи")
    for a, b in pairwise(stops):
        if a["check_out"] != b["check_in"]:
            errors.append(f"{a['name']} → {b['name']}: выезд {a['check_out']}, заезд {b['check_in']}")
    checked, landed = 0, None
    for leg in plan.get("legs") or []:
        departs, arrives = leg.get("departs"), leg.get("arrives")
        if not (departs and arrives):
            landed = None  # no ticket on this leg: the live search link picks its times
            continue
        checked += 1
        route = f"{leg.get('from')} → {leg.get('to')}"
        if landed and departs < landed:
            errors.append(f"{route}: вылет {departs} раньше прилёта {landed}")
        if (into := leg.get("to_stop")) is not None:
            stay, day, hour = stops[into], arrives[:10], arrives[11:]
            night_before = day == _next_day(stay["check_in"]) and hour <= NIGHT_ENDS
            if day != stay["check_in"] and not night_before:
                errors.append(f"{route}: прилёт {arrives}, заезд {stay['check_in']}")
        if (out := leg.get("from_stop")) is not None:
            stay, day, hour = stops[out], departs[:10], departs[11:]
            red_eye = day == _next_day(stay["check_out"]) and hour <= NIGHT_ENDS
            if day != stay["check_out"] and not red_eye:
                errors.append(f"{route}: вылет {departs}, выезд {stay['check_out']}")
        landed = arrives
    return errors, checked


def _arg_matches(actual, expected) -> bool:
    if isinstance(expected, dict) and "range" in expected:
        low, high = expected["range"]
        return isinstance(actual, int | float) and not isinstance(actual, bool) and low <= actual <= high
    if isinstance(expected, dict) and "any_of" in expected:
        return actual in expected["any_of"]
    if isinstance(expected, dict) and "contains" in expected:
        return isinstance(actual, list) and set(expected["contains"]) <= set(actual)
    return actual == expected


def _args_ok(calls: list[ToolCallRecord], expected: dict) -> bool:
    return any(
        all(_arg_matches(call.args.get(key), value) for key, value in expected.items())
        for call in calls
        if call.name == "search_destinations"
    )


def score(case: dict, transcript: Transcript) -> Score:
    failures: list[str] = []
    answer = "\n".join(transcript.replies)
    final = transcript.replies[-1] if transcript.replies else ""
    called = [c.name for c in transcript.calls]

    if transcript.error:
        failures.append(f"error: {transcript.error}")
    if not final.strip():
        failures.append("empty final answer")
    for tool in case.get("expect_tools", []):
        if tool not in called:
            failures.append(f"did not call {tool}")
    if case.get("expect_any_tool") and not set(case["expect_any_tool"]) & set(called):
        failures.append(f"called none of {case['expect_any_tool']}")
    if case.get("expect_args") and not _args_ok(transcript.calls, case["expect_args"]):
        seen = [c.args for c in transcript.calls if c.name == "search_destinations"]
        failures.append(
            f"no search matched {json.dumps(case['expect_args'], ensure_ascii=False)}; got {seen}"
        )
    # what the user got: the reply and what the cards, the route and the plan put on screen
    seen = "\n".join([final, *transcript.shown]).casefold()
    if case.get("expect_any") and not any(s.casefold() in seen for s in case["expect_any"]):
        failures.append(f"answer mentions none of {case['expect_any']}")
    if case.get("expect_plan") and not transcript.plans:
        failures.append("no trip plan on screen")
    stitch, legs = [], 0
    for plan in transcript.plans:
        found, checked = stitching_errors(plan)
        stitch, legs = stitch + found, legs + checked
    if stitch:
        failures.append(f"connection errors: {stitch}")
    for bad in case.get("forbid", []):
        if bad.casefold() in answer.casefold():
            failures.append(f"answer contains forbidden {bad!r}")

    # one clarification is one round: a card with its fields, or questions in a reply, answered at once
    questions = transcript.asked_rounds if transcript.asked_rounds is not None else count_questions(answer)
    if questions > case.get("max_questions", 1):
        failures.append(f"{questions} questions, max {case.get('max_questions', 1)}")
    if questions < case.get("min_questions", 0):
        failures.append(f"{questions} questions, expected at least {case['min_questions']}")
    if case.get("expect_source") and not SOURCE.search(final):
        failures.append("no source link or site named in the answer")

    ungrounded = ungrounded_numbers(answer, transcript.calls, "\n".join(case["turns"]))
    if ungrounded:
        failures.append(f"numbers not from any tool: {ungrounded}")

    first = next((t for t in transcript.first_token_s if t is not None), None)
    return Score(
        case_id=case["id"],
        category=case.get("category", ""),
        failures=failures,
        questions=questions,
        ungrounded=ungrounded,
        tools=called,
        first_token_s=first,
        total_s=transcript.total_s,
        research_from=research_sources(transcript.calls),
        llm_calls=transcript.llm_calls,
        input_tokens=transcript.input_tokens,
        cached_tokens=transcript.cached_tokens,
        output_tokens=transcript.output_tokens,
        first_pick_s=transcript.first_pick_s,
        first_step_s=transcript.first_step_s,
        card_fields=transcript.clarify_questions,
        plans=len(transcript.plans),
        legs_checked=legs,
        stitch_errors=stitch,
    )
