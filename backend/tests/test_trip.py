"""The trip brief and the per-chat tools: ask only what is missing, once, then show destination cards."""

import asyncio
import json

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.catalog.catalog import load_catalog
from app.catalog.seed import load_catalog_facts
from app.db import init_db
from app.tools import ToolRegistry
from app.trip import BriefPatch, TripBrief, TripState, merge, trip_tools
from app.trip.brief import assumptions, chips, missing, price_level, search_hint
from tests.conftest import FakeFlights, fresh_database, route

VAGUE = BriefPatch()
FULL = BriefPatch(destination="Турция", month=11, nights_min=7, adults=2, children=0, budget_total=250_000)


def brief(**fields) -> TripBrief:
    return merge(TripBrief(), BriefPatch(**fields))


def asked(b: TripBrief) -> TripBrief:
    return b.model_copy(update={"asked": True})


def test_should_miss_everything_for_a_vague_request():
    assert missing(merge(TripBrief(), VAGUE)) == ["origin", "vibe", "when", "travelers", "route", "budget"]


def test_should_ask_every_card_on_a_new_trip_even_when_the_request_says_it_all():
    # the user confirms what was understood in one tap: a misread budget or city is easy to fix
    assert missing(merge(TripBrief(), FULL)) == ["origin", "when", "travelers", "budget"]
    assert "vibe" in missing(brief(kinds=["sea"]))  # no place named: the kind of trip is asked too
    assert missing(asked(merge(TripBrief(), FULL))) == []  # after the cards nothing is asked again


def test_should_ask_for_the_party_when_a_child_has_no_age():
    b = asked(brief(kinds=["sea"], month=11, nights_min=7, adults=2, children=1, budget_level=1))

    assert missing(b) == ["travelers"]
    assert missing(merge(b, BriefPatch(children_ages=[5]))) == []


def test_should_count_nights_from_dates_and_take_the_month_from_them():
    b = brief(date_from="2026-11-10", date_to="2026-11-17")

    assert b.month == 11
    assert "when" not in missing(asked(b))
    assert "7 ночей" in chips(b)[0]


def test_should_never_erase_what_was_known_and_collect_wishes():
    b = brief(month=11, wishes=["без долгих перелётов"])

    b = merge(b, BriefPatch(adults=2, wishes=["всё включено", "без долгих перелётов"]))

    assert (b.month, b.adults) == (11, 2)
    assert b.wishes == ["без долгих перелётов", "всё включено"]


def test_should_keep_the_wishes_short_and_few():
    with pytest.raises(ValidationError):
        BriefPatch(wishes=["я" * 81])

    b = TripBrief()
    for n in range(15):
        b = merge(b, BriefPatch(wishes=[f"пожелание {n}"]))

    assert b.wishes == [f"пожелание {n}" for n in range(5, 15)]


def test_should_describe_the_brief_in_short_russian_phrases():
    b = brief(kinds=["sea"], month=11, nights_min=6, nights_max=8, adults=2, children=2, children_ages=[3, 7])

    assert chips(merge(b, BriefPatch(budget_level=2))) == [
        "Море",
        "Ноябрь · 6–8 ночей",
        "2 взрослых + 2 ребёнка (3 и 7 лет)",
        "Средний бюджет",
    ]


def test_should_turn_a_total_budget_into_a_price_level_per_person():
    assert price_level(brief(adults=2, budget_total=100_000)) == 1
    assert price_level(brief(adults=2, budget_total=250_000)) == 2
    assert price_level(brief(adults=1, budget_total=400_000)) == 3
    assert price_level(brief(budget_level=0)) is None


def test_should_refuse_a_budget_no_one_could_have():
    with pytest.raises(ValidationError):
        BriefPatch(budget_total=10**30)


def test_should_hint_search_filters_from_the_brief():
    b = merge(TripBrief(), FULL.model_copy(update={"children": 1, "children_ages": [4]}))

    hint = search_hint(b, load_catalog())

    assert hint == {"month": 11, "with_kids": True, "max_price_level": 2, "countries": ["Турция"]}


def test_should_state_assumptions_for_what_stayed_unanswered():
    assert assumptions(
        brief(kinds=["sea"], month=11, nights_min=7, adults=2, children=1, children_ages=[6])
    ) == ["бюджет не ограничен"]
    assert assumptions(brief(kinds=["city"], month=10, nights_min=8, adults=2)) == [
        "бюджет не ограничен",
        "один город, без переездов",
    ]


def test_should_ask_about_a_route_only_alongside_other_questions_and_when_it_fits():
    def asks(**fields) -> bool:
        return "route" in missing(brief(**fields))

    assert asks(kinds=["city"], month=10, nights_min=8)  # rides along with the party and budget questions
    assert not asks(
        kinds=["city"], month=10, nights_min=8, adults=2, children=0, budget_level=2
    )  # zero questions
    assert not asks(kinds=["city"], children=1)  # a route tires small children
    assert not asks(kinds=["city"], nights_min=3, nights_max=4)  # too short to move around
    assert not asks(kinds=["ski"])
    assert not asks(destination="Хургада")  # one named place
    assert asks(destination="Грузия")  # a country can be a route
    assert not asks(kinds=["city"], multi_city=False)


def test_should_hint_routes_when_the_user_wants_several_cities():
    hint = search_hint(brief(kinds=["city"], month=10, nights_min=9, multi_city=True), load_catalog())

    assert hint["multi_city"] is True and hint["nights"] == 9
    caucasus = search_hint(brief(destination="Кавказ", multi_city=True), load_catalog())
    assert sorted(caucasus["countries"]) == ["Азербайджан", "Армения", "Грузия"]
    assert chips(brief(kinds=["city"], multi_city=True))[-1] == "Несколько городов"


@pytest.fixture(scope="module")
def sessionmaker():
    db_url = fresh_database("trip")

    async def setup():
        engine = create_async_engine(db_url, poolclass=NullPool)
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
    assert json.loads(update.content)["missing"] == ["origin", "vibe", "when", "travelers", "budget"]
    assert update.preview == (
        "Понял: Море · Ноябрь · 1 ребёнок. Уточню: город вылета, тип отдыха, когда, кто едет, бюджет"
    )

    questions = [{"slot": "budget", "hint": "Вы написали «недорого»"}, {"slot": "travelers"}]
    asked = call(registry, "ask_user", {"intro": "Уточню пару моментов", "questions": questions})

    assert asked.ends_turn and asked.text == "Уточню пару моментов"
    # every card is shown, even those the model left out; known answers come prefilled
    assert [q["slot"] for q in asked.event["questions"]] == ["origin", "vibe", "when", "travelers", "budget"]
    assert asked.event["prefill"]["kinds"] == ["sea"] and asked.event["prefill"]["month"] == 11
    assert asked.event["questions"][4] == {
        "slot": "budget",
        "title": "Какой бюджет?",
        "hint": "Вы написали «недорого»",
    }
    assert asked.event["prefill"]["children"] == 1

    again = call(registry, "ask_user", {"intro": "Ещё вопрос", "questions": [{"slot": "budget"}]})
    assert again.event is None and not again.ends_turn
    assert "Already asked" in json.loads(again.content)["error"]
    assert json.loads(call(registry, "update_trip_brief", {}).content)["assumptions"]


def test_should_prefill_every_card_from_a_request_that_says_it_all(sessionmaker):
    state = TripState(merge(TripBrief(), FULL))
    registry = ToolRegistry(trip_tools(state, sessionmaker))

    result = call(registry, "ask_user", {"intro": "Проверьте, всё ли верно", "questions": []})

    assert [q["slot"] for q in result.event["questions"]] == ["origin", "when", "travelers", "budget"]
    prefill = result.event["prefill"]
    assert (prefill["month"], prefill["nights"], prefill["adults"], prefill["children"]) == (11, [7, 7], 2, 0)
    assert prefill["budget_total"] == 250_000 and prefill["origin"]["code"] == "MOW"


def test_should_start_over_for_a_new_trip(sessionmaker):
    state = TripState(merge(TripBrief(asked=True), FULL))
    registry = ToolRegistry(trip_tools(state, sessionmaker))

    result = json.loads(call(registry, "update_trip_brief", {"new_trip": True, "kinds": ["ski"]}).content)

    assert result["brief"] == {"kinds": ["ski"]} and not result["already_asked"]


def test_should_show_destination_cards_with_facts_for_the_month(sessionmaker):
    state = TripState(asked(brief(kinds=["sea"], month=11)))
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
    assert card["photo"]["url"].startswith("https://upload.wikimedia.org/") and card["photo"]["author"]
    assert result.event["summary"] == ["Море", "Ноябрь"]
    assert json.loads(result.content)["unknown"] == ["atlantis"]
    assert state.brief.shown == ["hurghada"]


def test_should_report_unknown_destinations_to_the_model(sessionmaker):
    registry = ToolRegistry(trip_tools(TripState(TripBrief(asked=True)), sessionmaker))

    result = call(registry, "show_destinations", {"intro": "Вот", "picks": [{"id": "atlantis", "why": "?"}]})

    assert result.event is None and "Unknown ids" in json.loads(result.content)["error"]


def test_should_find_routes_and_show_one_as_a_wide_card(sessionmaker):
    flights = FakeFlights({"EVN": route(240, price=30_000), "TBS": route(250), "MOW": route(200)})
    state = TripState(
        asked(brief(kinds=["city", "mountains"], month=10, nights_min=8, adults=2, multi_city=True))
    )
    registry = ToolRegistry(trip_tools(state, sessionmaker, flights=flights))

    found = call(registry, "search_routes", {"month": 10, "kinds": ["city", "mountains"]})
    routes = json.loads(found.content)["routes"]
    assert routes and all(2 <= len(r["stops"]) <= 3 for r in routes)
    pick = [s["id"] for s in routes[0]["stops"]]

    shown = call(
        registry,
        "show_destinations",
        {"intro": "Маршруты", "picks": [{"route": pick, "why": "Город и горы"}]},
    )

    [card] = shown.event["cards"]
    assert card["type"] == "route" and [s["id"] for s in card["stops"]] == pick
    assert sum(s["nights"] for s in card["stops"]) == 8
    assert card["legs"][0]["from"] == "Москва" and card["match"] > 0 and card["why"] == "Город и горы"
    assert any(s["photo"] for s in card["stops"])


def test_should_refuse_a_pick_that_is_neither_a_place_nor_a_route(sessionmaker):
    registry = ToolRegistry(trip_tools(TripState(TripBrief(asked=True)), sessionmaker))

    result = call(registry, "show_destinations", {"intro": "?", "picks": [{"why": "?"}]})

    assert not result.ok and result.event is None


def test_should_name_the_catalogue_place_the_user_asked_for(sessionmaker):
    registry = ToolRegistry(trip_tools(TripState(TripBrief(asked=True)), sessionmaker))

    named = json.loads(call(registry, "update_trip_brief", {"destination": "Анталья"}).content)
    country = json.loads(
        call(registry, "update_trip_brief", {"new_trip": True, "destination": "Турция"}).content
    )

    assert named["named_place"] == "antalya"
    assert "named_place" not in country


def test_should_never_start_over_on_the_turn_that_answers_the_cards(sessionmaker):
    state = TripState(
        merge(TripBrief(asked=True), BriefPatch(destination="Германия", month=12)), answered=True
    )
    registry = ToolRegistry(trip_tools(state, sessionmaker))

    result = json.loads(call(registry, "update_trip_brief", {"new_trip": True, "adults": 1}).content)

    assert result["brief"]["destination"] == "Германия" and result["already_asked"]  # kept, not wiped
