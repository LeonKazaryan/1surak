"""Runs the eval cases through the very path the chat takes: the app as `docker compose up` starts it (all
tools, real tickets, live hotels, the knowledge base with its embeddings), one chat per case, the model from .env.

    cd backend && python -m evals.run                 # all cases on the working database, as on the demo
    python -m evals.run --case golden --case typos    # some cases
    python -m evals.run --fresh                       # a clean database, as on the jury's first start
    python -m evals.run --model grok-…                # another model, same provider

A clarifying card is answered once with AUTO_ANSWER, as a user who lets the agent decide. Writes
evals/last_report.md (the table for the README) and full transcripts to .cache/evals/.
Costs real tokens: each case is one to three agent turns.
"""

import argparse
import asyncio
import json
import statistics
import sys
import time
import uuid
from contextvars import ContextVar
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from pathlib import Path

import anyio
from sqlalchemy.engine import make_url

from app.config import Settings
from app.db import reset_database
from app.flights.dictionary import find_city
from app.main import create_app
from app.tools import ToolRegistry
from evals.scoring import RECOMMENDATIONS, Score, ToolCallRecord, Transcript, count_questions, score

ROOT = Path(__file__).resolve().parent
CASES_PATH = ROOT / "cases.json"
REPORT_PATH = ROOT / "last_report.md"
README_PATH = ROOT.parent.parent / "README.md"
README_START, README_END = "<!-- eval:start -->", "<!-- eval:end -->"
METRICS_START, METRICS_END = "<!-- metrics -->", "<!-- /metrics -->"
WORK_DIR = ROOT.parent / ".cache" / "evals"
CASE_TIMEOUT_S = 300
# what shows the agent at work: a step, a note, the first words
STEPS = {"tool_preparing", "tool_start", "assistant_note", "assistant_token"}
AUTO_ANSWER = "Не важно, решай сам"
DEFAULT_ORIGIN = "MOW"

# Every tool call of the case being run, with the whole result the model saw: the chat's registry is built per
# turn (its trip and plan tools are bound to the chat), so the record is kept beside it, per task.
_recording: ContextVar[list[ToolCallRecord] | None] = ContextVar("recording", default=None)
_execute = ToolRegistry.execute


async def _recorded(self: ToolRegistry, name: str, raw_args: str):
    result = await _execute(self, name, raw_args)
    if (calls := _recording.get()) is not None:
        calls.append(ToolCallRecord(name=name, args=result.args, ok=result.ok, content=result.content))
    return result


ToolRegistry.execute = _recorded  # type: ignore[method-assign]


@dataclass
class Deps:
    """What the chat endpoint is given by the app."""

    sessionmaker: object
    llm: object
    tools: ToolRegistry
    flights: object = None
    hotels: object = None


def _origin_code(case: dict) -> str:
    named = case.get("origin")
    found = find_city(named) if named else None
    return found.code if found else DEFAULT_ORIGIN


async def run_case(case: dict, deps: Deps) -> Transcript:
    from app.chats.service import stream_reply  # after the app's own imports, as the app loads it

    transcript = Transcript()
    calls: list[ToolCallRecord] = []
    _recording.set(calls)
    chat_id = str(uuid.uuid4())
    started = time.monotonic()
    turns, answered = list(case["turns"]), False
    transcript.asked_rounds = 0
    try:
        with anyio.fail_after(CASE_TIMEOUT_S):
            while turns:
                text = turns.pop(0)
                turn_start, first, parts, asked = time.monotonic(), None, [], False
                async for event in stream_reply(
                    deps.sessionmaker,
                    deps.llm,
                    chat_id,
                    text,
                    tools=deps.tools,
                    origin_code=_origin_code(case),
                    flights=deps.flights,
                    hotels=deps.hotels,
                ):
                    kind = event["type"]
                    if kind in STEPS and transcript.first_step_s is None:
                        transcript.first_step_s = time.monotonic() - started
                    if kind == "assistant_token":
                        first = first if first is not None else time.monotonic() - turn_start
                        parts.append(event["text"])
                    elif kind == "clarify":
                        asked = True
                        transcript.clarify_questions += len(event.get("questions") or [])
                    elif kind in RECOMMENDATIONS and transcript.first_pick_s is None:
                        transcript.first_pick_s = time.monotonic() - started
                    if kind in RECOMMENDATIONS:
                        transcript.shown.extend(_shown(event))
                    if kind == "trip_plan":
                        transcript.plans.append(event)
                    elif kind == "usage":
                        transcript.llm_calls += event["llm_calls"]
                        transcript.input_tokens += event["input_tokens"]
                        transcript.cached_tokens += event["cached_tokens"]
                        transcript.output_tokens += event["output_tokens"]
                    elif kind == "error":
                        transcript.error = event.get("message")
                transcript.replies.append("".join(parts))
                transcript.first_token_s.append(first)
                transcript.asked_rounds += asked or count_questions(transcript.replies[-1]) > 0
                if asked and not turns and not answered:  # a user who lets the agent decide, once
                    turns, answered = [AUTO_ANSWER], True
    except Exception as error:  # noqa: BLE001  (a crashed case is a failed case, not a crashed run)
        transcript.error = f"{type(error).__name__}: {error}"[:300]
    transcript.calls = calls
    transcript.total_s = time.monotonic() - started
    return transcript


def _shown(event: dict) -> list[str]:
    """The names a recommendation puts on screen: the cards' places, the route's stops, the plan's hotels."""
    names = []
    for card in event.get("cards") or []:
        names += [card.get("name") or "", *(s.get("name") or "" for s in card.get("stops") or [])]
    for plan in event.get("plans") or []:
        names += [plan.get("name") or ""]
    for stop in event.get("stops") or []:
        names += [stop.get("name") or "", (stop.get("hotel") or {}).get("name") or ""]
    names += [h.get("name") or "" for h in event.get("hotels") or []]
    return [n for n in names if n]


def _fmt_s(value: float | None) -> str:
    return "–" if value is None else f"{value:.1f} с"


def _fmt_k(tokens: int) -> str:
    return f"{tokens / 1000:.1f}k"


def report(scores: list[Score], model: str, started: datetime, where: str = "") -> str:
    passed = sum(s.passed for s in scores)
    picks = [s.first_pick_s for s in scores if s.first_pick_s is not None]
    steps = [s.first_step_s for s in scores if s.first_step_s is not None]
    cards = [s.card_fields for s in scores if s.card_fields]
    firsts = [s.first_token_s for s in scores if s.first_token_s is not None]
    asked = sum(s.questions > 0 for s in scores)
    plans = sum(s.plans for s in scores)
    legs = sum(s.legs_checked for s in scores)
    stitch = sum(len(s.stitch_errors) for s in scores)
    ungrounded = sum(len(s.ungrounded) for s in scores)
    research = [source for s in scores for source in s.research_from]
    from_base = sum(source == "база знаний" for source in research)
    from_web = sum(source == "интернет" for source in research)
    tokens_in = sum(s.input_tokens for s in scores)
    cached = sum(s.cached_tokens for s in scores)
    tokens_out = sum(s.output_tokens for s in scores)
    llm_calls = sum(s.llm_calls for s in scores)
    lines = [
        f"# Eval: {passed} из {len(scores)} сценариев доведены до конца",
        "",
        (
            f"Модель `{model}`, запуск {started:%Y-%m-%d %H:%M}{f', {where}' if where else ''}. Кейсы из "
            "`evals/cases.json`: каждый проходит тем же путём, что и чат в интерфейсе, со всеми инструментами."
        ),
        "",
        METRICS_START,
        "| Метрика из ТЗ | Значение |",
        "|---|---|",
        f"| Доля доведённых до конца сценариев | {passed} из {len(scores)} ({passed / len(scores):.0%}) |",
        (
            f"| Уточнений на сценарий, в среднем | {statistics.fmean(s.questions for s in scores):.1f} "
            f"(спросили хоть что-то в {asked} из {len(scores)}; уточнение = один раунд вопросов) |"
        ),
        f"| Время до первой рекомендации, медиана | {_fmt_s(statistics.median(picks) if picks else None)} |",
        f"| Ошибки в стыковках | {stitch} в {plans} собранных планах, проверено {legs} перелётов и переездов |",
        "",
        "| Ещё | Значение |",
        "|---|---|",
        f"| Первый шаг агента на экране, медиана | {_fmt_s(statistics.median(steps) if steps else None)} |",
        f"| Первые слова ответа, медиана | {_fmt_s(statistics.median(firsts) if firsts else None)} |",
        (
            f"| Полей на карточке уточнения, в среднем | {statistics.fmean(cards) if cards else 0:.1f} "
            "(все на одной карточке) |"
        ),
        f"| Числа не из инструментов | {ungrounded} |",
        (
            f"| Поиск информации (research) | {len(research)} вызовов: из базы знаний {from_base}, "
            f"из интернета {from_web}, остальное без ответа |"
        ),
        (
            f"| Токены | вход {_fmt_k(tokens_in)} (из кэша {cached / max(tokens_in, 1):.0%}), "
            f"выход {_fmt_k(tokens_out)}, {llm_calls} вызовов модели |"
        ),
        METRICS_END,
        "",
        "| Кейс | Тип | Итог | Инструменты | Уточнений | Первая рекомендация | Всего | Что не так |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for s in scores:
        tools = ", ".join(dict.fromkeys(s.tools)) or "–"
        if s.research_from:
            tools += f" ({', '.join(s.research_from)})"
        why = "; ".join(s.failures).replace("|", "/") or ""
        mark = "✅" if s.passed else "❌"
        lines.append(
            f"| {s.case_id} | {s.category} | {mark} | {tools} | {s.questions} | "
            f"{_fmt_s(s.first_pick_s)} | {_fmt_s(s.total_s)} | {why} |"
        )
    return "\n".join(lines) + "\n"


def update_readme(text: str, readme: Path = README_PATH) -> bool:
    """The README's metrics, between its eval markers, from this run's report: the numbers never drift apart."""
    page = readme.read_text(encoding="utf-8") if readme.exists() else ""
    if README_START not in page or README_END not in page:
        return False
    tables = text.split(METRICS_START, 1)[1].split(METRICS_END, 1)[0].strip("\n")
    title = text.splitlines()[0].removeprefix("# Eval: ")
    model_line = text.splitlines()[2]
    block = f"{README_START}\n**{title}.** {model_line}\n\n{tables}\n{README_END}"
    head, rest = page.split(README_START, 1)
    readme.write_text(head + block + rest.split(README_END, 1)[1], encoding="utf-8")
    return True


async def provider_answers(settings: Settings) -> str | None:
    """None when the model answers; else why not, said before any case runs: no credits is not a failed case."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url or None, timeout=30)
    try:
        await client.chat.completions.create(
            model=settings.llm_model, messages=[{"role": "user", "content": "ok"}], max_tokens=1
        )
    except Exception as error:  # noqa: BLE001  (whatever it is, the run cannot go on)
        return f"{type(error).__name__}: {error}"[:400]
    return None


async def main(args: argparse.Namespace) -> int:
    # no climate prefetch: the app already running keeps it, and two would spend Open-Meteo's free limit twice
    settings = Settings(seed_catalog=True, fare_refresh_minutes=0, destination_prefetch="")
    if args.model:
        settings.llm_model = args.model
    if not (settings.llm_api_key and settings.llm_model):
        print(
            "Set LLM_API_KEY and LLM_MODEL in .env first: the stub reply can't be evaluated.", file=sys.stderr
        )
        return 2
    if why := await provider_answers(settings):
        print(f"The model does not answer, nothing was run: {why}", file=sys.stderr)
        return 2

    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))["cases"]
    if args.case:
        unknown = set(args.case) - {c["id"] for c in cases}
        if unknown:
            print(f"Unknown case ids: {sorted(unknown)}", file=sys.stderr)
            return 2
        cases = [c for c in cases if c["id"] in args.case]

    if args.fresh:  # a clean database: no cached tickets, hotels or web answers, as on the first start
        url = make_url(settings.database_url)
        settings.database_url = url.set(database=f"{url.database}_eval").render_as_string(hide_password=False)
        await reset_database(settings.database_url)
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    app = create_app(settings)
    started = datetime.now()
    async with app.router.lifespan_context(app):
        state = app.state
        deps = Deps(state.sessionmaker, state.llm, state.tools, state.flights, state.hotels)
        print(f"Running {len(cases)} cases on {settings.llm_model} (concurrency {args.concurrency})…")
        limit = asyncio.Semaphore(args.concurrency)

        async def one(case: dict) -> tuple[Score, Transcript]:
            async with limit:
                transcript = await run_case(case, deps)
            result = score(case, transcript)
            mark = "PASS" if result.passed else "FAIL"
            print(
                f"  {mark} {case['id']:26} {_fmt_s(result.total_s):>8} {_fmt_k(result.input_tokens):>7} in  "
                f"{'; '.join(result.failures)}",
                flush=True,
            )
            return result, transcript

        results = await asyncio.gather(*(one(c) for c in cases))

    scores = [r for r, _ in results]
    where = "чистая база, как при первом запуске" if args.fresh else "рабочая база с кэшем, как на демо"
    report_path = Path(args.report) if args.report else REPORT_PATH
    report_path.write_text(report(scores, settings.llm_model, started, where), encoding="utf-8")
    details = WORK_DIR / f"{started:%Y%m%d-%H%M%S}.json"
    details.write_text(
        json.dumps(
            [
                {"case": c, "score": asdict(s), "transcript": asdict(replace(t, plans=[]))}
                for c, (s, t) in zip(cases, results, strict=True)
            ],
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    passed = sum(s.passed for s in scores)
    if not args.case and not args.report and update_readme(report_path.read_text(encoding="utf-8")):
        print(f"README metrics updated from {report_path.name}")
    print(f"\n{passed}/{len(scores)} passed. Report: {report_path}  Transcripts: {details}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the agent eval against a real model.")
    parser.add_argument("--case", action="append", help="Run only this case id (repeatable).")
    parser.add_argument("--model", help="Override LLM_MODEL from .env.")
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument(
        "--fresh", action="store_true", help="Run on a clean database, as on the first start."
    )
    parser.add_argument("--report", help="Write the report here instead of evals/last_report.md.")
    sys.exit(asyncio.run(main(parser.parse_args())))
