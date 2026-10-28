"""End to end on the committed seed: load it into a fresh database and call the agent's tools."""

import asyncio
import json

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.catalog.seed import load_catalog_facts
from app.db import init_db
from app.facts.adapters.open_meteo_marine import monthly_sea_temp
from app.tools import build_registry
from tests.conftest import FakeFlights, fresh_database, route

# Tickets from Moscow by airport, as Aviasales would return them; places not listed have no flights.
FLIGHTS = FakeFlights(
    {
        "HRG": route(330, price=12_775),
        "SSH": route(300),
        "AYT": route(240),
        "HKT": route(570),
        "AER": route(150),
    }
)


@pytest.fixture(scope="module")
def registry():
    db_url = fresh_database("catalog")

    async def setup():
        engine = create_async_engine(db_url, poolclass=NullPool)
        await init_db(engine)
        sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
        first = await load_catalog_facts(sessionmaker)
        second = await load_catalog_facts(sessionmaker)
        return sessionmaker, engine, (first, second)

    sessionmaker, engine, loads = asyncio.run(setup())
    yield build_registry(sessionmaker, flights=FLIGHTS), loads
    asyncio.run(engine.dispose())


def call(registry, name: str, args: dict) -> tuple[dict, str]:
    result = asyncio.run(registry.execute(name, json.dumps(args, ensure_ascii=False)))
    assert result.ok, result.content
    return json.loads(result.content), result.preview


def test_should_load_the_seed_once_per_version(registry):
    _, loads = registry
    assert loads == (True, False)


def test_should_answer_the_golden_query_with_real_climate(registry):
    golden = {"month": 11, "min_sea_temp": 24, "max_flight_hours": 6, "with_kids": True, "max_price_level": 2}

    result, preview = call(registry[0], "search_destinations", golden)

    matches = {m["id"]: m for m in result["matches"]}
    assert "hurghada" in matches
    assert matches["hurghada"]["climate"]["море"] >= 24
    why = {m["id"]: m["why_not"] for m in result["near_misses"]}
    assert why["antalya"].startswith("море в ноябре около")
    assert "phuket" not in matches and "sochi" not in matches
    assert preview.startswith("Подходят: ")
    assert matches["hurghada"]["flight"]["price_rub"] == 12_775  # the real ticket reaches the model
    assert result["from"] == "Москва"


def test_should_return_a_full_card_by_name(registry):
    card, preview = call(registry[0], "get_destination", {"place": "Хургада"})

    assert card["id"] == "hurghada"
    assert len(card["by_month"]) == 12
    assert card["wikidata"].startswith("https://www.wikidata.org/wiki/Q")
    assert preview == "Хургада, Египет"


def test_should_list_known_ids_for_an_unknown_place(registry):
    card, _ = call(registry[0], "get_destination", {"place": "Атлантида"})

    assert "Unknown destination" in card["error"] and "hurghada" in card["error"]


def test_should_turn_daily_sea_temperature_into_monthly_means():
    payload = {
        "daily_units": {"sea_surface_temperature_mean": "°C"},
        "daily": {
            "time": ["2024-01-01", "2024-01-02", "2024-02-01", "2024-03-01"],
            "sea_surface_temperature_mean": [20.0, 22.0, 18.0, None],
        },
    }
    from datetime import UTC, datetime

    facts = monthly_sea_temp("Q1", payload, datetime(2026, 10, 25, tzinfo=UTC))

    assert [(f.period, f.value) for f in facts] == [("m1", 21.0), ("m2", 18.0)]
    assert {f.source for f in facts} == {"open-meteo-marine"}


def test_should_find_tickets_for_a_city_outside_the_catalogue(registry):
    FLIGHTS.table["IST"] = route(345, price=10_558, airline="PC")

    result, preview = call(registry[0], "search_flights", {"destination": "Стамбул", "month": 11})

    assert result["tickets"]["airline_name"] == "Pegasus Airlines"
    assert result["tickets"]["logo"] == "https://pics.avs.io/64/64/PC.png"
    assert preview == "Москва → Стамбул: от 10\u00a0558\u00a0₽, прямой"


def test_should_send_to_the_live_search_when_the_cache_has_no_fare(registry):
    result, preview = call(registry[0], "search_flights", {"destination": "Магадан"})

    assert "tickets" not in result  # empty fields are dropped
    assert result["search_link"].startswith("https://www.aviasales.ru/search/MOW")
    assert preview.endswith("цены в живом поиске") and "Aviasales" not in preview
