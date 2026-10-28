"""The eval scorer and runner, driven by the scripted fake model, so they work before anyone adds a key."""

import asyncio
import json

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db import init_db
from app.llm import ToolCall
from evals.run import CASES_PATH, Deps, report, run_case
from evals.scoring import (
    ToolCallRecord,
    Transcript,
    count_questions,
    score,
    stitching_errors,
    ungrounded_numbers,
)
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


def test_should_run_a_case_through_the_chat_and_record_what_it_did(db_url):
    from app.catalog.tools import catalog_tools
    from app.tools import ToolRegistry

    llm = FakeLLM(
        rounds=[
            [ToolCall(id="c1", name="search_destinations", arguments='{"month": 11, "kinds": ["sea"]}')],
            ["Смотрю."],
            ["Вот так. Сколько лет ребёнку?"],
        ]
    )
    case = {"id": "two", "turns": ["к морю в ноябре"], "origin": "Казань"}

    async def go():
        engine = create_async_engine(db_url)
        await init_db(engine)
        sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
        try:
            return await run_case(case, Deps(sessionmaker, llm, ToolRegistry(catalog_tools(sessionmaker))))
        finally:
            await engine.dispose()

    transcript = asyncio.run(go())

    assert transcript.error is None
    assert transcript.replies == ["Вот так. Сколько лет ребёнку?"]
    assert [c.name for c in transcript.calls] == ["search_destinations"]
    assert json.loads(transcript.calls[0].content)["from"] == "Казань"  # the case's departure city
    assert transcript.asked_rounds == 1 and transcript.first_step_s is not None


def test_should_find_nights_without_a_bed_and_flights_that_miss_the_stay():
    stops = [
        {"name": "Рим", "check_in": "2026-11-21", "check_out": "2026-11-25"},
        {"name": "Барселона", "check_in": "2026-11-25", "check_out": "2026-12-02"},
    ]
    legs = [
        {
            "from": "Астана",
            "to": "Рим",
            "to_stop": 0,
            "departs": "2026-11-21T05:05",
            "arrives": "2026-11-21T08:25",
        },
        {
            "from": "Рим",
            "to": "Барселона",
            "from_stop": 0,
            "to_stop": 1,
            "departs": "2026-11-25T22:55",
            "arrives": "2026-11-26T00:45",
        },  # lands after midnight: the night before is booked
        {
            "from": "Барселона",
            "to": "Астана",
            "from_stop": 1,
            "departs": "2026-12-02T15:00",
            "arrives": "2026-12-03T06:00",
        },
    ]
    assert stitching_errors({"stops": stops, "legs": legs}) == ([], 3)

    broken = [{**stops[0], "check_out": "2026-11-24"}, stops[1]]
    late = [legs[0], {**legs[1], "departs": "2026-11-26T10:00", "arrives": "2026-11-26T12:00"}, legs[2]]
    errors, _ = stitching_errors({"stops": broken, "legs": late})
    assert errors == [
        "Рим → Барселона: выезд 2026-11-24, заезд 2026-11-25",
        "Рим → Барселона: прилёт 2026-11-26T12:00, заезд 2026-11-25",
        "Рим → Барселона: вылет 2026-11-26T10:00, выезд 2026-11-24",
    ]


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

    assert text.startswith("# Eval: 1 из 1 сценариев доведены до конца")
    assert "Уточнений на сценарий" in text and "Ошибки в стыковках" in text and "| golden |" in text


def test_should_read_a_dash_between_numbers_as_a_range_not_a_minus():
    calls = [search_call({}, {"near": "море около 23.5 °C", "other": 23.7})]

    assert ungrounded_numbers("море около 23,5-23,7 °C, ночью -3 °C", calls) == ["-3 °"]


def test_should_write_the_metrics_into_the_readme_between_its_markers(tmp_path):
    from datetime import datetime

    from evals.run import update_readme

    readme = tmp_path / "README.md"
    readme.write_text(
        "# Проект\n\n<!-- eval:start -->\nстарое\n<!-- eval:end -->\n\n## Дальше\n", encoding="utf-8"
    )
    text = report(
        [score(GOLDEN, Transcript(replies=["Хургада."], first_token_s=[1.0]))], "m", datetime(2026, 10, 29)
    )

    assert update_readme(text, readme)
    page = readme.read_text(encoding="utf-8")
    assert "старое" not in page and "| Доля доведённых до конца сценариев |" in page
    assert page.endswith("<!-- eval:end -->\n\n## Дальше\n") and "| Кейс |" not in page
