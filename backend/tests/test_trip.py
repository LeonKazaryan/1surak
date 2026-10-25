"""The trip brief and the per-chat tools: ask only what is missing, once, then show destination cards."""

import asyncio
import json

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.catalog.catalog import load_catalog
from app.catalog.seed import load_catalog_facts
from app.db import init_db
from app.tools import ToolRegistry
from app.trip import BriefPatch, TripBrief, TripState, merge, trip_tools
from app.trip.brief import assumptions, chips, missing, price_level, search_hint
from tests.conftest import FakeFlights, route

VAGUE = BriefPatch()
FULL = BriefPatch(
    destination="Турция", month=11, nights_min=7, adults=2, children=0, budget_total_rub=250_000
)


def brief(**fields) -> TripBrief:
    return merge(TripBrief(), BriefPatch(**fields))


def test_should_miss_everything_for_a_vague_request():
    assert missing(merge(TripBrief(), VAGUE)) == ["vibe", "when", "travelers", "budget"]


def test_should_miss_nothing_when_the_request_says_it_all():
    assert missing(merge(TripBrief(), FULL)) == []


def test_should_ask_for_the_party_when_a_child_has_no_age():
    b = brief(kinds=["sea"], month=11, nights_min=7, adults=2, children=1, budget_level=1)

    assert missing(b) == ["travelers"]
    assert missing(merge(b, BriefPatch(children_ages=[5]))) == []


def test_should_count_nights_from_dates_and_take_the_month_from_them():
    b = brief(date_from="2026-11-10", date_to="2026-11-17")

    assert b.month == 11
    assert "when" not in missing(b)
    assert "7 ночей" in chips(b)[0]


def test_should_never_erase_what_was_known_and_collect_wishes():
    b = brief(month=11, wishes=["без долгих перелётов"])

    b = merge(b, BriefPatch(adults=2, wishes=["всё включено", "без долгих перелётов"]))

    assert (b.month, b.adults) == (11, 2)
    assert b.wishes == ["без долгих перелётов", "всё включено"]


def test_should_describe_the_brief_in_short_russian_phrases():
    b = brief(kinds=["sea"], month=11, nights_min=6, nights_max=8, adults=2, children=2, children_ages=[3, 7])

    assert chips(merge(b, BriefPatch(budget_level=2))) == [
        "Море",
        "Ноябрь · 6–8 ночей",
        "2 взрослых + 2 ребёнка (3 и 7 лет)",
        "Средний бюджет",
    ]


def test_should_turn_a_total_budget_into_a_price_level_per_person():
    assert price_level(brief(adults=2, budget_total_rub=100_000)) == 1
    assert price_level(brief(adults=2, budget_total_rub=250_000)) == 2
    assert price_level(brief(adults=1, budget_total_rub=400_000)) == 3
    assert price_level(brief(budget_level=0)) is None


def test_should_hint_search_filters_from_the_brief():
    b = merge(TripBrief(), FULL.model_copy(update={"children": 1, "children_ages": [4]}))

    hint = search_hint(b, load_catalog())

    assert hint == {"month": 11, "with_kids": True, "max_price_level": 2, "countries": ["Турция"]}


def test_should_state_assumptions_for_what_stayed_unanswered():
    assert assumptions(brief(kinds=["sea"], month=11, nights_min=7, adults=2)) == ["бюджет не ограничен"]


@pytest.fixture(scope="module")
def sessionmaker(tmp_path_factory):
    db_url = f"sqlite+aiosqlite:///{tmp_path_factory.mktemp('trip') / 'trip.db'}"

    async def setup():
        engine = create_async_engine(db_url)
        await init_db(engine)
        maker = async_sessionmaker(engine, expire_on_commit=False)
        await load_catalog_facts(maker)
        return engine, maker

    engine, maker = asyncio.run(setup())
    yield maker
    asyncio.run(engine.dispose())


def call(registry: ToolRegistry, name: str, args: dict):
    return asyncio.run(registry.execute(name, json.dumps(args, ensure_ascii=False)))


def test_should_ask_only_missing_slots_once_and_end_the_turn(sessionmaker):
    state = TripState(TripBrief())
    registry = ToolRegistry(trip_tools(state, sessionmaker))

    update = call(registry, "update_trip_brief", {"kinds": ["sea"], "month": 11, "children": 1})
    assert json.loads(update.content)["missing"] == ["when", "travelers", "budget"]
    assert update.preview == "Понял: Море · Ноябрь · 1 ребёнок. Уточню: когда, кто едет, бюджет"

    questions = [
        {"slot": "budget", "hint": "Вы написали «недорого»"},
        {"slot": "vibe"},
        {"slot": "travelers"},
    ]
    asked = call(registry, "ask_user", {"intro": "Уточню пару моментов", "questions": questions})

    assert asked.ends_turn and asked.text == "Уточню пару моментов"
    assert [q["slot"] for q in asked.event["questions"]] == ["travelers", "budget"]  # vibe is known
    assert asked.event["questions"][1] == {
        "slot": "budget",
        "title": "Какой бюджет?",
        "hint": "Вы написали «недорого»",
    }
    assert asked.event["prefill"]["children"] == 1

    again = call(registry, "ask_user", {"intro": "Ещё вопрос", "questions": [{"slot": "budget"}]})
    assert again.event is None and not again.ends_turn
    assert "Already asked" in json.loads(again.content)["error"]
    assert json.loads(call(registry, "update_trip_brief", {}).content)["assumptions"]


def test_should_refuse_to_ask_when_nothing_is_missing(sessionmaker):
    state = TripState(merge(TripBrief(), FULL))
    registry = ToolRegistry(trip_tools(state, sessionmaker))

    result = call(registry, "ask_user", {"intro": "Вопрос", "questions": [{"slot": "budget"}]})

    assert result.event is None and "Nothing to ask" in json.loads(result.content)["error"]


def test_should_start_over_for_a_new_trip(sessionmaker):
    state = TripState(merge(TripBrief(asked=True), FULL))
    registry = ToolRegistry(trip_tools(state, sessionmaker))

    result = json.loads(call(registry, "update_trip_brief", {"new_trip": True, "kinds": ["ski"]}).content)

    assert result["brief"] == {"kinds": ["ski"]} and not result["already_asked"]


def test_should_show_destination_cards_with_facts_for_the_month(sessionmaker):
    state = TripState(brief(kinds=["sea"], month=11))
    registry = ToolRegistry(
        trip_tools(state, sessionmaker, flights=FakeFlights({"HRG": route(330, price=12_775)}))
    )
    picks = [
        {"id": "hurghada", "why": "Тёплое море и 5 часов лёту", "tradeoff": "Ветрено"},
        {"id": "atlantis", "why": "Нет такого"},
        {"id": "Хургада", "why": "Дубль по имени"},
    ]

    result = call(registry, "show_destinations", {"intro": "Вот что нашёл", "picks": picks})

    assert result.ends_turn and result.text == "Вот что нашёл"
    [card] = result.event["cards"]
    assert card["id"] == "hurghada" and card["why"] == "Тёплое море и 5 часов лёту"
    assert card["climate"]["month"] == "ноябрь" and card["climate"]["sea"] >= 24
    assert card["country_code"] == "EG" and card["flight_hours"] == 5.5
    assert card["flight"]["price_rub"] == 12_775 and card["flight"]["airline_name"] == "Аэрофлот"
    assert result.event["summary"] == ["Море", "Ноябрь"]
    assert json.loads(result.content)["unknown"] == ["atlantis"]
    assert state.brief.shown == ["hurghada"]


def test_should_report_unknown_destinations_to_the_model(sessionmaker):
    registry = ToolRegistry(trip_tools(TripState(TripBrief()), sessionmaker))

    result = call(registry, "show_destinations", {"intro": "Вот", "picks": [{"id": "atlantis", "why": "?"}]})

    assert result.event is None and "Unknown ids" in json.loads(result.content)["error"]
