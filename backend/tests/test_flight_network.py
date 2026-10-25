"""The route map from the seed, airport codes read as cities, and fares kept in the database."""

import asyncio
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.catalog.catalog import load_catalog
from app.db import init_db
from app.flights import city, city_code, network
from app.flights.client import TravelpayoutsFlights
from app.flights.fares import FareStore
from app.flights.network import Network, estimate_minutes
from tests.test_flights import ROWS

NOW = datetime(2026, 10, 25, 12, tzinfo=UTC)


def test_should_read_an_airport_code_as_its_city():
    assert city_code("svo") == "MOW" and city_code("PEK") == "BJS" and city_code("AYT") == "AYT"
    assert city("SAW").name == "Стамбул"
    assert city_code("zzz") == "ZZZ"


def test_should_place_every_catalogue_airport_on_the_map():
    lost = [p.airport for p in load_catalog().places if p.airport and city(p.airport) is None]

    assert lost == []


def test_should_know_the_direct_flights_from_the_seed():
    n = network()
    cities, links = n.size

    assert cities > 2000 and links > 20000
    link = n.link("SVO", "IST")  # an airport code finds the city's link
    assert link.origin.code == "MOW" and link.destination.code == "IST" and "TK" in link.airlines
    assert 1600 < link.km < 1900 and 2 * 60 < link.minutes < 3 * 60
    out = n.links_from("NQZ")
    assert len(out) > 10 and [x.km for x in out] == sorted(x.km for x in out)
    assert all(x.destination.code == "IST" for x in n.links_to("IST"))


def test_should_estimate_a_flight_from_the_distance():
    n = Network({"MOW": {"IST": "TK", "XXX": "TK"}}, {c: city(c) for c in ("MOW", "IST")})

    assert n.direct("MOW", "IST") and not n.direct("IST", "MOW")
    assert n.size == (1, 1)  # a link to an unknown city is dropped
    assert 9 * 60 < n.estimate("MOW", "HKT") < 10.5 * 60  # real: about 9 h 30 min
    assert n.estimate("MOW", "MOW") is None and n.estimate("MOW", "nowhere") is None
    assert estimate_minutes(0) == 30


class Clock:
    def __init__(self):
        self.now = NOW

    def __call__(self):
        return self.now


async def _fares_scenario(db_url: str):
    engine = create_async_engine(db_url)
    await init_db(engine)
    store = FareStore(async_sessionmaker(engine, expire_on_commit=False))
    asked = []

    def handler(request: httpx.Request) -> httpx.Response:
        asked.append(request.url.params["destination"])
        if request.url.params["destination"] == "HKT":
            return httpx.Response(500)
        rows = ROWS if request.url.params["destination"] == "IST" else []
        return httpx.Response(200, json={"data": rows})

    def fresh_client(clock):
        transport = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        return TravelpayoutsFlights("token", transport, store=store, clock=clock)

    clock = Clock()
    try:
        first = await fresh_client(clock).routes("SVO", ["SAW", "AER", "HKT"], 11)
        restarted = await fresh_client(clock).routes("MOW", ["IST", "AER", "HKT"], 11)
        clock.now += timedelta(hours=7)
        expired = await fresh_client(clock).route("MOW", "IST", 11)
        return first, restarted, expired, asked
    finally:
        await engine.dispose()


def test_should_keep_fares_across_restarts_until_they_expire(tmp_path):
    first, restarted, expired, asked = asyncio.run(
        _fares_scenario(f"sqlite+aiosqlite:///{tmp_path / 'f.db'}")
    )

    # SVO and SAW are asked as their cities; the result stays keyed by what the caller passed
    assert first["SAW"].cheapest.price == 9000 and first["AER"] is None and first["HKT"] is None
    # after a «restart» the fares come from the table: IST with its tickets, AER as known «no tickets»;
    # HKT failed, so it was not stored and is asked again
    assert restarted["IST"].direct.price == 10558 and restarted["AER"] is None
    assert asked[:4] == ["AER", "HKT", "IST", "HKT"]
    assert expired.cheapest.price == 9000 and asked[4:] == ["IST"]
