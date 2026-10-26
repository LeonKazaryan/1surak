"""Destinations from the route map: places beyond the catalogue, their fetched climate, search and plans."""

import asyncio
import json
from datetime import UTC, datetime

import httpx
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.catalog.catalog import load_catalog
from app.catalog.seed import load_catalog_facts
from app.catalog.tools import catalog_tools
from app.db import init_db
from app.destinations import catalog_cities, discovered_place, kinds_from, load_discovered, reachable
from app.destinations.climate import ClimateFetcher, windows
from app.flights import current_origin, network
from app.plan.places import place_info
from app.plan.tools import plan_tools
from app.tools import ToolRegistry
from app.trip import TripState
from tests.conftest import fresh_database
from tests.test_plan_tools import COUPLE, TICKETS, call, sessionmaker  # noqa: F401  (the fixture)

NOW = datetime(2026, 10, 26, 12, tzinfo=UTC)


def test_should_make_a_place_of_any_city_the_route_map_flies_to():
    tashkent = discovered_place("TAS")

    assert tashkent.id == "city-tas" and not tashkent.verified and tashkent.airport == "TAS"
    assert tashkent.country.visa == "visa_free"  # Uzbekistan is a catalogue country: its checked rule
    assert discovered_place("BJV") is None  # Bodrum is the catalogue's, with its checked facts
    unknown = discovered_place("LIM")  # Lima: a country we never checked
    assert unknown.country.visa == "unknown" and "не проверяли" in unknown.country.visa_note
    assert (
        load_catalog().find("Ташкент").id == "city-tas" and load_catalog().find("city-tas").name == "Ташкент"
    )
    assert str(place_info("city-tas").tz) == "Asia/Tashkent" and place_info("city-tas").airport


def test_should_list_the_direct_destinations_beyond_the_catalogue_nearest_first():
    found = reachable(network(), "ALA")

    assert "TAS" in found and "ALA" not in found
    assert not set(found) & catalog_cities()
    km = [next(link.km for link in network().links_from("ALA") if link.destination.code == c) for c in found]
    assert km == sorted(km)


def test_should_tell_the_kind_of_trip_from_the_facts():
    assert kinds_from({"coastal": True, "sea_tempm7": 27.0}) == ("sea", "city")
    assert kinds_from({"coastal": True, "sea_tempm7": 14.0}) == ("city",)  # a cold coast is not a beach trip
    assert kinds_from({"elevation": 1600}) == ("city", "mountains")


def climate_answer(request: httpx.Request) -> httpx.Response:
    params = request.url.params
    start, end = params["start_date"], params["end_date"]
    days = [f"{start[:8]}{d:02d}" for d in range(int(start[8:]), int(end[8:]) + 1)]
    month = int(start[5:7])
    if "marine" in str(request.url):
        sea = [None] * len(days) if params["latitude"].startswith("41") else [20.0 + month] * len(days)
        return httpx.Response(
            200,
            json={
                "daily": {"time": days, "sea_surface_temperature_mean": sea},
                "daily_units": {"sea_surface_temperature_mean": "°C"},
            },
        )
    daily = {
        "time": days,
        "temperature_2m_max": [10.0 + 2 * month] * len(days),
        "temperature_2m_min": [month * 1.0] * len(days),
        "precipitation_sum": [0.0] * len(days),
    }
    units = {"temperature_2m_max": "°C", "temperature_2m_min": "°C", "precipitation_sum": "mm"}
    return httpx.Response(200, json={"elevation": 455, "daily": daily, "daily_units": units})


async def _fetch_scenario(db_url: str):
    engine = create_async_engine(db_url, poolclass=NullPool)
    await init_db(engine)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    await load_catalog_facts(maker)
    asked = []

    def handler(request):
        asked.append(str(request.url))
        return climate_answer(request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    fetcher = ClimateFetcher(maker, client, per_minute=60_000, clock=lambda: NOW)
    try:
        queued = await fetcher.ensure(["TAS", "TAS", "LIM"])
        await fetcher.drain()
        again = await fetcher.ensure(["TAS"])  # already in the facts table: nothing to fetch
        async with maker() as db:
            snapshots = {s.place.id: s for s in await load_discovered(db, ["TAS", "LIM", "FRU"], NOW)}
        tools = ToolRegistry(catalog_tools(maker, now=lambda: NOW, flights=TICKETS, climate=fetcher))
        token = current_origin.set("ALA")
        try:
            hot = await tools.execute(
                "search_destinations",
                json.dumps({"month": 7, "min_air_temp": 20, "countries": ["Узбекистан"]}),
            )
        finally:
            current_origin.reset(token)
        return queued, again, asked, snapshots, json.loads(hot.content), maker
    finally:
        await engine.dispose()


def test_should_fetch_a_cities_climate_once_and_search_it():
    queued, again, asked, snapshots, hot, _ = asyncio.run(_fetch_scenario(fresh_database("dest")))

    assert queued == 2 and again == 0
    tashkent_calls = [u for u in asked if "latitude=41.299" in u]
    assert len(tashkent_calls) == 12 + 1  # twelve windows of air, one sea probe inland
    assert len(windows()) == 12
    tas = snapshots["city-tas"]
    assert tas.climate[7]["air_max"] == 24.0 and "sea" not in tas.place.kinds
    lima = snapshots["city-lim"]
    assert "sea" in lima.place.kinds and lima.climate[1]["sea_temp"] == 21.0 and lima.visa_rule == "unknown"
    assert "city-fru" not in snapshots  # no climate fetched for it: not offered yet
    # in July the fake Tashkent is 24 °C by day: it matches «20 °C or warmer», marked as from the route map
    tashkent = next(m for m in hot["matches"] if m["name"] == "Ташкент")
    assert tashkent["from_route_map"] and tashkent["id"] == "city-tas"
    assert hot["route_map"]["destinations_from_your_city"] > 0 and hot["route_map"]["looked_at"] >= 1


def test_should_plan_a_whole_trip_to_a_route_map_city(sessionmaker):  # noqa: F811
    state = TripState(COUPLE)
    registry = ToolRegistry(plan_tools(state, sessionmaker, flights=TICKETS))

    built = json.loads(call(registry, "build_trip", {"id": "city-tas"}).content)

    assert built["name"] == "Ташкент" and built["stops"][0]["hotel"]["name"]
    assert built["days"]


def test_should_read_a_region_as_every_country_in_it():
    from app.destinations.regions import countries_in, country_names

    europe = countries_in("хочу по Европе")
    assert {"Германия", "Франция", "Италия", "Сербия"} <= set(europe)
    assert "Россия" not in europe and "Турция" not in europe  # Antalya is in Asia
    assert countries_in("юго-восточная азия") and "Китай" not in countries_in("юго-восточная азия")
    assert country_names("Германия") == ["Германия"] and countries_in("Турция") is None


class LiveAnswers:
    def __init__(self, fail=False):
        self.calls = 0
        self.fail = fail

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        if self.fail:
            return httpx.Response(500)
        if "city-directions" in str(request.url):
            return httpx.Response(
                200, json={"data": {"PAR": {"destination": "PAR"}, "IST": {"destination": "IST"}}}
            )
        rows = [
            {"destination": "VIE", "value": 30000},
            {"destination": "HAM", "value": 25000},
            {"destination": "VIE", "value": 28000},
        ]
        return httpx.Response(200, json={"data": rows})


def test_should_list_where_people_fly_now_and_cache_it():
    from app.destinations.live import LiveDirections

    answers = LiveAnswers()
    live = LiveDirections("token", httpx.AsyncClient(transport=httpx.MockTransport(answers)))

    async def run():
        return await live.destinations("NQZ"), await live.destinations("NQZ")

    first, again = asyncio.run(run())
    assert first == ["PAR", "IST", "HAM", "VIE"] and again == first and answers.calls == 2  # cheapest first
    broken = LiveDirections("token", httpx.AsyncClient(transport=httpx.MockTransport(LiveAnswers(fail=True))))
    assert asyncio.run(broken.destinations("NQZ")) == []


class FixedDirections:
    async def destinations(self, origin):
        return ["VIE", "PAR"]


async def _europe_scenario(db_url: str):
    engine = create_async_engine(db_url, poolclass=NullPool)
    await init_db(engine)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    await load_catalog_facts(maker)
    client = httpx.AsyncClient(transport=httpx.MockTransport(climate_answer))
    fetcher = ClimateFetcher(maker, client, per_minute=60_000, clock=lambda: NOW)
    tools = ToolRegistry(
        catalog_tools(maker, now=lambda: NOW, flights=TICKETS, climate=fetcher, directions=FixedDirections())
    )
    from app.destinations.regions import countries_in

    token = current_origin.set("NQZ")
    try:
        result = await tools.execute(
            "search_destinations", json.dumps({"month": 7, "countries": countries_in("Европа"), "limit": 10})
        )
        await fetcher.drain()
        return json.loads(result.content)
    finally:
        current_origin.reset(token)
        await engine.dispose()


def test_should_offer_european_cities_people_fly_to_on_the_first_search():
    found = asyncio.run(_europe_scenario(fresh_database("europe")))

    names = [m["name"] for m in found["matches"]]
    assert "Вена" in names and "Париж" in names  # live destinations, climate fetched before answering
    assert all(m.get("from_route_map") for m in found["matches"] if m["name"] in ("Вена", "Париж"))
    assert found["route_map"]["live_from_aviasales"] == 2 and found["route_map"]["climate_fetched_now"] >= 2


def test_should_give_the_route_map_up_to_half_of_the_results():
    from app.catalog.search import mixed

    class P:
        def __init__(self, name, verified):
            self.place = type("Place", (), {"verified": verified, "name": name})()

    near = [P(f"каталог {i}", True) for i in range(6)]
    far = [P(f"город {i}", False) for i in range(3)]
    order = near + far  # the catalogue's resorts are nearer, so they rank first

    shown = mixed(order, 5, order.index)
    assert [p.place.name for p in shown] == ["каталог 0", "каталог 1", "город 0", "город 1", "город 2"]
    assert mixed(near, 5, near.index) == near[:5]  # nothing from the route map: the catalogue as before


def test_should_read_abroad_from_the_users_own_country():
    from app.catalog.search import SearchQuery, Snapshot, in_scope

    kostanay, tashkent = Snapshot(discovered_place("KSN")), Snapshot(discovered_place("TAS"))
    token = current_origin.set("NQZ")
    try:
        abroad, home = SearchQuery(region="abroad"), SearchQuery(region="russia")
        assert not in_scope(kostanay, abroad) and in_scope(tashkent, abroad)
        assert in_scope(kostanay, home) and not in_scope(tashkent, home)
    finally:
        current_origin.reset(token)


def test_should_show_a_named_country_as_near_misses_when_the_budget_rules_it_out():
    from app.catalog.search import SearchQuery, Snapshot
    from app.catalog.tools import shortlist

    frankfurt = Snapshot(discovered_place("FRA"))  # price level 2 (not «недорого»)
    frankfurt.visa_rule = "visa_free"
    found = shortlist([frankfurt], SearchQuery(countries=["Германия"], max_price_level=1))

    assert found == [frankfurt]  # priced and shown with its reason, not dropped
