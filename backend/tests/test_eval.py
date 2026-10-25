"""The eval scorer and runner, driven by the scripted fake model, so they work before anyone adds a key."""

import asyncio
import json

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db import init_db
from app.llm import ToolCall
from evals.run import CASES_PATH, report, run_case
from evals.scoring import ToolCallRecord, Transcript, count_questions, score, ungrounded_numbers
from tests.conftest import FakeLLM

GOLDEN = json.loads(CASES_PATH.read_text(encoding="utf-8"))["cases"][0]


def search_call(args: dict, content: dict) -> ToolCallRecord:
    return ToolCallRecord("search_destinations", args, True, json.dumps(content, ensure_ascii=False))


def test_should_load_cases_with_unique_ids():
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))["cases"]
    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids)) and GOLDEN["id"] == "golden"
    assert all(c["turns"] for c in cases)


def test_should_count_questions_per_sentence():
    assert count_questions("Сколько лет ребёнку?? И откуда летите? Пока считаю для Москвы.") == 2


def test_should_flag_numbers_no_tool_or_user_gave():
    calls = [search_call({}, {"climate": {"море": 26}, "flight_hours": 5.0})]

    flagged = ungrounded_numbers(
        "Море около 26 °C, лететь 5 ч, днём 31°, до 6 часов", calls, "не больше 6 часов"
    )

    assert flagged == ["31°"]


def test_should_pass_a_good_golden_run():
    args = {"month": 11, "with_kids": True, "min_sea_temp": 24, "max_flight_hours": 6}
    transcript = Transcript(
        replies=["Подойдут Хургада и Шарм-эш-Шейх: море около 26 °C, перелёт 5 ч. Сколько лет ребёнку?"],
        calls=[search_call(args, {"matches": [{"climate": {"море": 26}, "flight_hours": 5.0}]})],
        first_token_s=[2.0],
        total_s=4.0,
    )

    result = score(GOLDEN, transcript)

    assert result.passed, result.failures
    assert result.questions == 1


def test_should_explain_each_failed_check():
    transcript = Transcript(
        replies=["Сочи прекрасен, море 25 °C. Сколько вас? Когда? Откуда?"],
        calls=[search_call({"month": 11}, {"matches": []})],
        first_token_s=[None],
    )

    failures = score(GOLDEN, transcript).failures

    assert any("no search matched" in f for f in failures)
    assert any("mentions none of" in f for f in failures)
    assert any("3 questions" in f for f in failures)
    assert any("numbers not from any tool" in f for f in failures)


def test_should_match_ranges_any_of_and_contains():
    case = {
        "id": "x",
        "turns": ["?"],
        "expect_args": {"month": {"any_of": [12, 1]}, "kinds": {"contains": ["ski"]}},
    }
    good = Transcript(replies=["ок"], calls=[search_call({"month": 1, "kinds": ["ski", "mountains"]}, {})])
    bad = Transcript(replies=["ок"], calls=[search_call({"month": 3, "kinds": ["ski"]}, {})])

    assert score(case, good).passed
    assert not score(case, bad).passed


def test_should_run_a_two_turn_case_and_record_tool_results(db_url):
    llm = FakeLLM(
        rounds=[
            [ToolCall(id="c1", name="search_destinations", arguments='{"month": 11, "kinds": ["sea"]}')],
            ["Смотрю."],
            ["Вот так."],
        ]
    )
    case = {"id": "two", "turns": ["к морю в ноябре", "а почему?"], "origin": "Казань"}

    async def go():
        engine = create_async_engine(db_url)
        await init_db(engine)
        try:
            return await run_case(case, llm, async_sessionmaker(engine, expire_on_commit=False))
        finally:
            await engine.dispose()

    transcript = asyncio.run(go())

    assert transcript.error is None
    assert transcript.replies == ["Смотрю.", "Вот так."]
    assert [c.name for c in transcript.calls] == ["search_destinations"]
    assert json.loads(transcript.calls[0].content)["from"] == "Москва"
    second_turn = llm.conversations[2]
    assert [m["role"] for m in second_turn[1:]] == ["user", "assistant", "user"]
    assert second_turn[-1]["content"] == "а почему?\n\nГород вылета: Казань"


def test_should_render_a_report_with_the_brief_metrics():
    passed = score(
        GOLDEN,
        Transcript(
            replies=["Хургада. Сколько лет ребёнку?"],
            calls=[
                search_call({"month": 11, "with_kids": True, "min_sea_temp": 24, "max_flight_hours": 5}, {})
            ],
            first_token_s=[1.5],
        ),
    )

    from datetime import datetime

    text = report([passed], "test-model", datetime(2026, 10, 25, 12, 0))

    assert text.startswith("# Eval: 1/1 сценариев пройдено")
    assert "Уточняющих вопросов в среднем" in text and "| golden |" in text


def test_should_read_a_dash_between_numbers_as_a_range_not_a_minus():
    calls = [search_call({}, {"near": "море около 23.5 °C", "other": 23.7})]

    assert ungrounded_numbers("море около 23,5-23,7 °C, ночью -3 °C", calls) == ["-3 °"]
