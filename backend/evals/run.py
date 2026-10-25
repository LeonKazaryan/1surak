"""Runs the eval cases through the real agent, tools and model, and scores them.

    cd backend && python -m evals.run                 # all cases, model from .env
    python -m evals.run --case golden --case typos    # some cases
    python -m evals.run --model gpt-…                 # another model, same provider

Writes evals/last_report.md (the table for the README) and full transcripts to .cache/evals/.
Costs real tokens: each case is one to two agent turns.
"""

import argparse
import asyncio
import json
import statistics
import sys
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import anyio
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import agent
from app.catalog.seed import load_catalog_facts
from app.catalog.tools import catalog_tools
from app.config import Settings
from app.db import ensure_database, init_db, reset_database
from app.kb.embeddings import Embedder, FastEmbedder
from app.kb.page import page_tools_for
from app.kb.seed import backfill_embeddings, load_kb_seed
from app.kb.tools import read_page_tool, research_tool
from app.kb.web import web_search_for
from app.llm import StubLLM, build_llm
from app.tools import ToolRegistry, ToolResult
from evals.scoring import Score, ToolCallRecord, Transcript, score

ROOT = Path(__file__).resolve().parent
CASES_PATH = ROOT / "cases.json"
REPORT_PATH = ROOT / "last_report.md"
WORK_DIR = ROOT.parent / ".cache" / "evals"
CASE_TIMEOUT_S = 180


class RecordingRegistry(ToolRegistry):
    """The real tools, plus a record of what each call returned to the model."""

    def __init__(self, tools):
        super().__init__(tools)
        self.calls: list[ToolCallRecord] = []

    async def execute(self, name: str, raw_args: str) -> ToolResult:
        result = await super().execute(name, raw_args)
        self.calls.append(ToolCallRecord(name=name, args=result.args, ok=result.ok, content=result.content))
        return result


async def run_case(
    case: dict, llm, sessionmaker, web=None, pages=None, embedder: Embedder | None = None
) -> Transcript:
    extra = [read_page_tool(sessionmaker, pages, embedder=embedder)] if pages else []
    tools = RecordingRegistry(
        [*catalog_tools(sessionmaker), research_tool(sessionmaker, web, embedder=embedder), *extra]
    )
    transcript = Transcript()
    history: list[dict] = []
    started = time.monotonic()
    try:
        with anyio.fail_after(CASE_TIMEOUT_S):
            for user_text in case["turns"]:
                turn_start, first, parts = time.monotonic(), None, []
                turns = [*history, {"role": "user", "content": user_text}]
                async for event in agent.run(llm, turns, tools, origin=case.get("origin")):
                    if event["type"] == "assistant_token":
                        first = first if first is not None else time.monotonic() - turn_start
                        parts.append(event["text"])
                    elif event["type"] == "usage":
                        transcript.llm_calls += event["llm_calls"]
                        transcript.input_tokens += event["input_tokens"]
                        transcript.cached_tokens += event["cached_tokens"]
                        transcript.output_tokens += event["output_tokens"]
                reply = "".join(parts)
                transcript.replies.append(reply)
                transcript.first_token_s.append(first)
                history = [*turns, {"role": "assistant", "content": reply}]
    except Exception as error:  # noqa: BLE001  (a crashed case is a failed case, not a crashed run)
        transcript.error = f"{type(error).__name__}: {error}"[:300]
    transcript.calls = tools.calls
    transcript.total_s = time.monotonic() - started
    return transcript


def _fmt_s(value: float | None) -> str:
    return "–" if value is None else f"{value:.1f} с"


def _fmt_k(tokens: int) -> str:
    return f"{tokens / 1000:.1f}k"


def report(scores: list[Score], model: str, started: datetime) -> str:
    passed = sum(s.passed for s in scores)
    firsts = [s.first_token_s for s in scores if s.first_token_s is not None]
    ungrounded = sum(len(s.ungrounded) for s in scores)
    research = [source for s in scores for source in s.research_from]
    from_base = sum(source == "база знаний" for source in research)
    from_web = sum(source == "интернет" for source in research)
    tokens_in = sum(s.input_tokens for s in scores)
    cached = sum(s.cached_tokens for s in scores)
    tokens_out = sum(s.output_tokens for s in scores)
    llm_calls = sum(s.llm_calls for s in scores)
    lines = [
        f"# Eval: {passed}/{len(scores)} сценариев пройдено",
        "",
        f"Модель `{model}`, запуск {started:%Y-%m-%d %H:%M}, кейсы из `evals/cases.json`.",
        "",
        "| Метрика | Значение |",
        "|---|---|",
        f"| Сценарии пройдены | {passed} из {len(scores)} ({passed / len(scores):.0%}) |",
        f"| Уточняющих вопросов в среднем | {statistics.fmean(s.questions for s in scores):.1f} |",
        f"| До первого ответа, медиана | {_fmt_s(statistics.median(firsts) if firsts else None)} |",
        f"| Числа не из инструментов | {ungrounded} |",
        "| Ошибки стыковок | проверим, когда появятся билеты и отели |",
        (
            f"| Поиск информации (research) | {len(research)} вызовов: из базы знаний {from_base}, "
            f"из интернета {from_web}, остальное без ответа |"
        ),
        (
            f"| Токены | вход {_fmt_k(tokens_in)} (из кэша {cached / max(tokens_in, 1):.0%}), "
            f"выход {_fmt_k(tokens_out)}, {llm_calls} вызовов модели; "
            f"на сценарий {_fmt_k(tokens_in // len(scores))} входа |"
        ),
        "",
        "| Кейс | Тип | Итог | Инструменты | Вопросов | Первый ответ | Всего | Токены (вход/выход) | Что не так |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for s in scores:
        tools = ", ".join(dict.fromkeys(s.tools)) or "–"
        if s.research_from:
            tools += f" ({', '.join(s.research_from)})"
        why = "; ".join(s.failures).replace("|", "/") or ""
        mark = "✅" if s.passed else "❌"
        lines.append(
            f"| {s.case_id} | {s.category} | {mark} | {tools} | {s.questions} | "
            f"{_fmt_s(s.first_token_s)} | {_fmt_s(s.total_s)} | "
            f"{_fmt_k(s.input_tokens)}/{_fmt_k(s.output_tokens)} | {why} |"
        )
    return "\n".join(lines) + "\n"


async def main(args: argparse.Namespace) -> int:
    settings = Settings()
    if args.model:
        settings.llm_model = args.model
    llm = build_llm(settings)
    if isinstance(llm, StubLLM):
        print(
            "Set LLM_API_KEY and LLM_MODEL in .env first: the stub reply can't be evaluated.", file=sys.stderr
        )
        return 2

    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))["cases"]
    if args.case:
        unknown = set(args.case) - {c["id"] for c in cases}
        if unknown:
            print(f"Unknown case ids: {sorted(unknown)}", file=sys.stderr)
            return 2
        cases = [c for c in cases if c["id"] in args.case]

    WORK_DIR.mkdir(parents=True, exist_ok=True)
    main_db = make_url(settings.database_url)
    db_url = main_db.set(database=f"{main_db.database}_eval").render_as_string(hide_password=False)
    if args.keep_db:
        await ensure_database(db_url)
    else:  # a fresh base each run, so web results from a previous run don't help
        await reset_database(db_url)
    engine = create_async_engine(db_url)
    await init_db(engine)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    await load_catalog_facts(sessionmaker)
    await load_kb_seed(sessionmaker)
    embedder = FastEmbedder() if settings.embeddings else None
    await backfill_embeddings(sessionmaker, embedder)
    web = web_search_for(settings, llm)
    pages = page_tools_for(settings, llm)

    started = datetime.now()
    print(f"Running {len(cases)} cases on {settings.llm_model} (concurrency {args.concurrency})…")
    limit = asyncio.Semaphore(args.concurrency)

    async def one(case: dict) -> tuple[Score, Transcript]:
        async with limit:
            transcript = await run_case(case, llm, sessionmaker, web, pages, embedder)
        result = score(case, transcript)
        mark = "PASS" if result.passed else "FAIL"
        print(
            f"  {mark} {case['id']:26} {_fmt_s(result.total_s):>8} {_fmt_k(result.input_tokens):>7} in  "
            f"{'; '.join(result.failures)}",
            flush=True,
        )
        return result, transcript

    results = await asyncio.gather(*(one(c) for c in cases))
    await engine.dispose()

    scores = [r for r, _ in results]
    report_path = Path(args.report) if args.report else REPORT_PATH
    report_path.write_text(report(scores, settings.llm_model, started), encoding="utf-8")
    details = WORK_DIR / f"{started:%Y%m%d-%H%M%S}.json"
    details.write_text(
        json.dumps(
            [
                {"case": c, "score": asdict(s), "transcript": asdict(t)}
                for c, (s, t) in zip(cases, results, strict=True)
            ],
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    passed = sum(s.passed for s in scores)
    if pages.extractor and pages.extractor.input_tokens:
        print(
            f"read_page extraction: {pages.extractor.input_tokens} input, "
            f"{pages.extractor.output_tokens} output tokens"
        )
    print(f"\n{passed}/{len(scores)} passed. Report: {report_path}  Transcripts: {details}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the agent eval against a real model.")
    parser.add_argument("--case", action="append", help="Run only this case id (repeatable).")
    parser.add_argument("--model", help="Override LLM_MODEL from .env.")
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--keep-db", action="store_true", help="Reuse the knowledge base from the last run.")
    parser.add_argument("--report", help="Write the report here instead of evals/last_report.md.")
    sys.exit(asyncio.run(main(parser.parse_args())))
