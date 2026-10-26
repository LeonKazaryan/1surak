"""Prices in the user's own currency: chosen by the departure city, converted only where they are shown."""

import asyncio
import json
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.db import init_db
from app.flights import currency_for, current_origin
from app.money import CURRENCIES, RUB, current_currency
from app.tools import ToolRegistry
from app.trip import BriefPatch, TripBrief, TripState, merge, trip_tools
from app.trip.brief import chips, price_level
from tests.conftest import FakeFlights, fresh_database, route

KZT = CURRENCIES["KZT"]


@pytest.fixture(scope="module")
def sessionmaker_trip():
    engine = create_async_engine(fresh_database("money"), poolclass=NullPool)
    asyncio.run(init_db(engine))
    yield async_sessionmaker(engine, expire_on_commit=False)
    asyncio.run(engine.dispose())


@pytest.mark.parametrize(
    ("origin", "code"),
    [
        ("NQZ", "KZT"),
        ("MOW", "RUB"),
        ("MSQ", "BYN"),
        ("TAS", "UZS"),
        ("IST", "USD"),
        ("XXX", "RUB"),
        (None, "RUB"),
    ],
)
def test_should_pick_the_currency_from_the_departure_city(origin, code):
    assert currency_for(origin).code == code


def test_should_show_roubles_in_the_users_currency():
    assert RUB.format(7_707) == "7\u00a0707\u00a0₽"
    assert KZT.format(7_707) == "42\u00a0865\u00a0₸"
    assert KZT.to_rub(42_865) == 7_707


def test_should_turn_a_budget_in_tenge_into_a_price_level():
    def level(total: int) -> int | None:
        return price_level(
            merge(TripBrief(), BriefPatch(adults=1, budget_total=total, budget_currency="KZT"))
        )

    assert level(300_000) == 1  # about 54 000 ₽
    assert level(400_000) == 2  # about 72 000 ₽


def test_should_say_the_budget_in_the_currency_the_user_named():
    brief = merge(TripBrief(), BriefPatch(budget_total=500_000, budget_currency="KZT"))

    assert "до 500\u00a0000\u00a0₸" in chips(brief)


def _in_tenge(coro_factory):
    async def run():
        tokens = current_currency.set(KZT), current_origin.set("NQZ")
        try:
            return await coro_factory()
        finally:
            current_currency.reset(tokens[0])
            current_origin.reset(tokens[1])

    return asyncio.run(run())


def test_should_take_a_budget_without_a_currency_as_the_users_own(sessionmaker_trip):
    state = TripState(TripBrief())
    registry = ToolRegistry(trip_tools(state, sessionmaker_trip))

    _in_tenge(lambda: registry.execute("update_trip_brief", json.dumps({"budget_total": 400_000})))

    assert state.brief.budget_currency == "KZT"


def test_should_draw_cards_and_questions_in_the_users_currency(sessionmaker_trip):
    state = TripState(merge(TripBrief(asked=True), BriefPatch(kinds=["sea"], month=11)))
    flights = FakeFlights({"HRG": route(330, price=7_707)})
    registry = ToolRegistry(trip_tools(state, sessionmaker_trip, flights=flights))
    picks = {"intro": "Вот", "picks": [{"id": "hurghada", "why": "Тепло"}]}

    shown = _in_tenge(lambda: registry.execute("show_destinations", json.dumps(picks, ensure_ascii=False)))
    asked = _in_tenge(
        lambda: ToolRegistry(trip_tools(TripState(TripBrief()), sessionmaker_trip)).execute(
            "ask_user", json.dumps({"intro": "Уточню", "questions": [{"slot": "budget"}]})
        )
    )

    assert shown.event["currency"] == KZT.view() and asked.event["currency"] == KZT.view()
    assert shown.event["cards"][0]["flight"]["price"] == "42\u00a0865\u00a0₸"


def test_should_start_the_app_when_money_loads_before_the_flights_package():
    backend = Path(__file__).parents[1]
    command = [sys.executable, "-c", "import app.agent"]
    result = subprocess.run(command, cwd=backend, capture_output=True, text=True, check=False)

    assert result.returncode == 0, result.stderr
