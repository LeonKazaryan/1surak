"""The tools that turn a pick into a trip: build_trip assembles it in code, show_trip puts it on screen."""

import asyncio
import json

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.catalog.seed import load_catalog_facts
from app.db import init_db
from app.plan.tools import plan_tools
from app.tools import ToolRegistry
from app.trip import BriefPatch, TripBrief, TripState, merge, trip_tools
from tests.conftest import FakeFlights, fresh_database
from tests.test_plan_assemble import flights

# after the question cards: building a trip before them is refused (see test_should_ask_before_building)
COUPLE = merge(
    TripBrief(asked=True), BriefPatch(month=11, nights_min=7, nights_max=7, adults=2, budget_level=2)
)
TICKETS = FakeFlights(
    {
        "AYT": flights(("2026-11-06T09:40:00+03:00", "AYT", 18_000, 240)),
        "MOW": flights(("2026-11-13T15:00:00+03:00", "MOW", 17_000, 240)),
    }
)


@pytest.fixture(scope="module")
def sessionmaker():
    db_url = fresh_database("plan")

    async def setup():
        engine = create_async_engine(db_url, poolclass=NullPool)
        await init_db(engine)
        maker = async_sessionmaker(engine, expire_on_commit=False)
        await load_catalog_facts(maker)
        return engine, maker

    engine, maker = asyncio.run(setup())
    yield maker
    asyncio.run(engine.dispose())


def tools(state: TripState, sessionmaker) -> ToolRegistry:
    return ToolRegistry(
        [*trip_tools(state, sessionmaker, flights=TICKETS), *plan_tools(state, sessionmaker, flights=TICKETS)]
    )


def call(registry: ToolRegistry, name: str, args: dict):
    return asyncio.run(registry.execute(name, json.dumps(args, ensure_ascii=False)))


def test_should_ask_before_building(sessionmaker):
    # «Казань на выходные вдвоём»: a named place, but the cards of a new trip come first
    state = TripState(COUPLE.model_copy(update={"asked": False}))

    built = call(tools(state, sessionmaker), "build_trip", {"id": "kazan"})

    assert "ask_user" in json.loads(built.content)["error"]


def test_should_build_the_trip_then_show_it_as_a_plan(sessionmaker):
    state = TripState(COUPLE)
    registry = tools(state, sessionmaker)

    built = call(registry, "build_trip", {"id": "antalya"})
    result = json.loads(built.content)
    assert built.ok and result["dates"] == "6–13 ноября, 7 ночей"
    assert result["stops"][0]["hotel"]["name"]
    assert registry.get("build_trip").then == "show_trip"

    shown = call(registry, "show_trip", {"intro": "Собрал для вас неделю в Анталье."})

    assert shown.ends_turn and shown.text == "Собрал для вас неделю в Анталье."
    event = shown.event
    assert event["type"] == "trip_plan" and event["id"] == "antalya"
    assert event["stops"][0]["hotel"]["demo"] and event["days"] and event["costs"]["total"] > 0
    assert event["currency"]["code"] == "RUB"
    assert state.brief.plan["id"] == "antalya"


def test_should_build_a_route_by_its_id(sessionmaker):
    state = TripState(COUPLE.model_copy(update={"multi_city": True}))

    built = call(tools(state, sessionmaker), "build_trip", {"id": "tbilisi+yerevan"})

    assert [s["name"] for s in json.loads(built.content)["stops"]] == ["Тбилиси", "Ереван"]


def test_should_tell_the_model_about_an_unknown_pick(sessionmaker):
    registry = tools(TripState(COUPLE), sessionmaker)

    built = call(registry, "build_trip", {"id": "atlantis"})
    shown = call(registry, "show_trip", {"intro": "Вот"})

    assert "Unknown" in json.loads(built.content)["error"]
    assert shown.event is None and "build_trip" in json.loads(shown.content)["error"]


def test_should_rebuild_with_another_hotel_and_say_what_changed(sessionmaker):
    state = TripState(COUPLE)
    registry = tools(state, sessionmaker)
    call(registry, "build_trip", {"id": "antalya"})
    call(registry, "show_trip", {"intro": "План"})

    current = json.loads(call(registry, "update_trip_brief", {}).content)["current_plan"]
    other = current["alternatives"][0]
    again = TripState(state.brief)  # the next turn starts from the saved brief
    rebuilt = json.loads(
        call(tools(again, sessionmaker), "build_trip", {"id": "antalya", "hotels": [other["id"]]}).content
    )

    assert rebuilt["stops"][0]["hotel"]["id"] == other["id"]
    assert any(other["name"] in change for change in rebuilt["changes"])
