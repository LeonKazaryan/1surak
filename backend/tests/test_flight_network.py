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
from app.flights.freshness import LATER, MONTHS_OUT, SOON, RateLimit, fare_ttl
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
        clock.now += timedelta(hours=4)  # past the 3 h expiry of a trip next week, but not stale for long
        later = fresh_client(clock)
        stale = await later.route("MOW", "IST", 11)
        asked_before_refresh = len(asked)
        await later.settle()
        clock.now += timedelta(days=3)  # too old to show: wait for a fresh answer
        too_old = fresh_client(clock)
        await too_old.route("MOW", "AER", 11)
        return first, restarted, (stale, asked_before_refresh), asked
    finally:
        await engine.dispose()


def test_should_keep_fares_across_restarts_until_they_expire(tmp_path):
    first, restarted, (stale, asked_before_refresh), asked = asyncio.run(
        _fares_scenario(f"sqlite+aiosqlite:///{tmp_path / 'f.db'}")
    )

    # SVO and SAW are asked as their cities; the result stays keyed by what the caller passed
    assert first["SAW"].cheapest.price == 9000 and first["AER"] is None and first["HKT"] is None
    # after a «restart» the fares come from the table: IST with its tickets, AER as known «no tickets»;
    # HKT failed, so it was not stored and is asked again
    assert restarted["IST"].direct.price == 10558 and restarted["AER"] is None
    assert asked[:4] == ["AER", "HKT", "IST", "HKT"]
    # an expired price is served at once and replaced in the background
    assert stale.cheapest.price == 9000 and asked_before_refresh == 4 and asked[4] == "IST"
    assert asked[5:] == ["AER"]


def test_should_keep_a_price_longer_the_further_away_the_trip_is():
    assert fare_ttl("", NOW) == SOON
    assert fare_ttl("2026-11", NOW) == SOON  # starts in a week
    assert fare_ttl("2026-12", NOW) == MONTHS_OUT
    assert fare_ttl("2027-03", NOW) == LATER
    assert fare_ttl("2026-10", NOW) == SOON  # the current month


def test_should_space_out_calls_past_the_burst():
    ticks = [0.0]
    slept = []

    async def run():
        limit = RateLimit(per_minute=60, burst=2, clock=lambda: ticks[0])
        original = asyncio.sleep

        async def fake_sleep(seconds):
            slept.append(round(seconds, 3))
            ticks[0] += seconds
            await original(0)

        asyncio.sleep = fake_sleep
        try:
            for _ in range(4):
                await limit.wait()
        finally:
            asyncio.sleep = original

    asyncio.run(run())

    assert slept == [1.0, 1.0]  # two at once, then one a second


def test_should_share_one_request_between_concurrent_lookups():
    asked = []

    async def handler(request: httpx.Request) -> httpx.Response:
        asked.append(request.url.params["destination"])
        await asyncio.sleep(0.01)
        return httpx.Response(200, json={"data": ROWS})

    async def run():
        flights = TravelpayoutsFlights("token", httpx.AsyncClient(transport=httpx.MockTransport(handler)))
        return await asyncio.gather(
            flights.route("MOW", "IST", 11),
            flights.route("SVO", "SAW", 11),
            flights.routes("MOW", ["IST", "AYT"], 11),
        )

    one, two, both = asyncio.run(run())

    assert sorted(asked) == ["AYT", "IST"]
    assert one is two is both["IST"]


def test_should_learn_links_from_the_tickets_it_sees():
    n = Network({"MOW": {"IST": "TK", "AYT": "SU"}}, {c: city(c) for c in ("MOW", "IST", "AYT", "HKT")})

    n.observe("MOW", "HKT", "SU", NOW)  # direct ticket on a route the seed lacks
    n.observe("SVO", "AYT", None, NOW)  # tickets, but only with transfers
    n.observe("MOW", "IST", "PC", NOW)
    n.observe("MOW", "IST", None, NOW + timedelta(days=1))  # a direct ticket once is proof enough

    assert n.link("MOW", "HKT").status == "seen" and n.link("MOW", "HKT").airlines == ("SU",)
    assert n.link("MOW", "AYT").status == "doubtful" and n.direct("MOW", "AYT")
    ist = n.link("MOW", "IST")
    assert ist.status == "seen" and ist.airlines == ("PC", "TK")
    assert n.size == (1, 3)


async def _evidence_scenario(db_url: str):
    engine = create_async_engine(db_url)
    await init_db(engine)
    store = FareStore(async_sessionmaker(engine, expire_on_commit=False))
    transport = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"data": ROWS}))
    )
    try:
        await TravelpayoutsFlights("token", transport, store=store, clock=Clock()).route("NQZ", "BKK", 11)
        n = Network({}, {c: city(c) for c in ("NQZ", "BKK")})
        await TravelpayoutsFlights("token", transport, store=store, network=n).start()
        return n
    finally:
        await engine.dispose()


def test_should_rebuild_what_it_learnt_from_the_stored_fares(tmp_path):
    n = asyncio.run(_evidence_scenario(f"sqlite+aiosqlite:///{tmp_path / 'e.db'}"))

    link = n.link("NQZ", "BKK")
    assert link.status == "seen" and link.airlines == ("PC",)
