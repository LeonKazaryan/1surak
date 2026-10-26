"""Real hotels from the directory, estimated offers behind a cache, more hotels on request, honest claims."""

import asyncio
import json
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.catalog.catalog import load_catalog
from app.db import init_db
from app.hotels import MIN_REAL, EstimatedOffers, HotelSource, Listed, Offer, StayQuery, find, listed
from app.hotels.cache import CachedOffers, OfferStore
from app.hotels.directory import hotel_id
from app.plan.checks import arrival_checks
from app.plan.hotels import Party, Wishes, choose_hotel
from app.plan.places import place_info
from app.plan.tools import plan_tools
from app.tools import ToolRegistry
from app.trip import BriefPatch, TripBrief, TripState, merge
from tests.conftest import Ticket, fresh_database
from tests.test_plan_tools import COUPLE, TICKETS, call, sessionmaker  # noqa: F401  (the fixture)

CATALOG = load_catalog()
KAZAN = CATALOG.find("kazan")
NOW = datetime(2026, 10, 26, 12, tzinfo=UTC)
STAY = StayQuery("kazan", date(2026, 11, 6), 3)


def hotel(i: int, stars: int | None = 4, centre_m: int = 800) -> Listed:
    return Listed(
        f"kazan-hq{i}", "kazan", f"Отель {i}", stars, 55.79, 49.11, centre_m, None, "https://wikidata"
    )


def test_should_have_real_hotels_for_most_places():
    covered = [p.id for p in CATALOG.places if len(listed(p.id)) >= MIN_REAL]

    assert len(covered) >= 30
    kazan = listed("kazan")
    assert kazan and all(h.id.startswith("kazan-h") and h.source_url for h in kazan)
    assert find(kazan[0].id) == kazan[0]
    assert (
        hotel_id("kazan", {"osm": "way/12"}) == "kazan-how12"
        and hotel_id("kazan", {"qid": "Q7"}) == "kazan-hq7"
    )
    photos = [h.photo for p in CATALOG.places for h in listed(p.id) if h.photo]
    assert photos and all(
        p["author"] and p["license"] and p["url"].startswith("https://upload.wikimedia.org") for p in photos
    )


def test_should_estimate_offers_by_stars_and_say_they_are_estimates():
    found = asyncio.run(EstimatedOffers().offers(KAZAN, [hotel(1, 3), hotel(2, 5)], STAY))

    three, five = found["kazan-hq1"], found["kazan-hq2"]
    assert [o.meal for o in three] == ["room_only", "breakfast"]
    assert five[0].night_rub > three[0].night_rub
    assert all(o.kind == "estimate" and not o.terms_known for o in three + five)
    assert asyncio.run(EstimatedOffers().offers(KAZAN, [hotel(1, 3)], STAY)) == {"kazan-hq1": three}  # stable


def test_should_use_real_hotels_where_there_are_enough_and_demo_ones_elsewhere():
    party = Party(2)
    real = asyncio.run(HotelSource().hotels(KAZAN, date(2026, 11, 6), 3, party))
    few = HotelSource(listing=lambda pid: (hotel(1),))
    demo = asyncio.run(few.hotels(KAZAN, date(2026, 11, 6), 3, party))

    assert real and all(h.real and h.rating is None for h in real)
    assert demo and not any(h.real for h in demo)


def test_should_claim_nothing_about_a_real_hotel_it_does_not_know():
    hotels = asyncio.run(
        HotelSource(listing=lambda pid: tuple(hotel(i) for i in range(5))).hotels(
            KAZAN, date(2026, 11, 6), 3, Party(2, (4,))
        )
    )
    pick = choose_hotel(hotels, Party(2, (4,)), Wishes(pets=True, all_inclusive=True), 2, 3)

    assert pick.best.misses == [] and pick.excluded == []  # no «нет детского клуба», no «без животных»
    assert any("животными" in u and "уточним" in u for u in pick.unmet)
    assert any("всё включено" in u and "уточним" in u for u in pick.unmet)
    late = Ticket("A", "B", "SU", "1", "2026-11-06T23:30:00+03:00", 9000, 0, 60, "/x")
    [check] = arrival_checks(late, pick.best.hotel, place_info("kazan"), 30)
    assert "обычно" in check.title and "ресепшен" not in check.text


class CountingOffers:
    def __init__(self, fail: bool = False):
        self.calls = 0
        self.fail = fail

    async def offers(self, place, hotels, stay):
        self.calls += 1
        await asyncio.sleep(0.01)
        if self.fail:
            raise RuntimeError("provider down")
        return {
            h.id: [Offer(h.id, "breakfast", 5000 + self.calls, kind="real", terms_known=True, source="test")]
            for h in hotels
        }


async def _cache_scenario(db_url: str):
    engine = create_async_engine(db_url, poolclass=NullPool)
    await init_db(engine)
    store = OfferStore(async_sessionmaker(engine, expire_on_commit=False))
    clock = [NOW]
    provider = CountingOffers()
    hotels = [hotel(1), hotel(2)]
    try:
        first = CachedOffers(provider, store, clock=lambda: clock[0])
        both = await asyncio.gather(first.offers(KAZAN, hotels, STAY), first.offers(KAZAN, hotels, STAY))
        restarted = CachedOffers(provider, store, clock=lambda: clock[0])
        again = await restarted.offers(KAZAN, hotels, STAY)
        calls_before_expiry = provider.calls
        clock[0] += timedelta(hours=4)  # a stay in two weeks keeps its prices three hours
        stale = await restarted.offers(KAZAN, hotels, STAY)
        await restarted.settle()
        broken = CachedOffers(CountingOffers(fail=True), None, clock=lambda: clock[0])
        nothing = await broken.offers(KAZAN, hotels, STAY)
        return both, again, calls_before_expiry, stale, provider.calls, nothing
    finally:
        await engine.dispose()


def test_should_cache_offers_share_requests_and_refresh_them_when_old():
    both, again, before, stale, after, nothing = asyncio.run(_cache_scenario(fresh_database("hotels")))

    assert (
        both[0] is both[1] and before == 1
    )  # two searches at once, one request; the restart reads the table
    assert again["kazan-hq1"][0].night_rub == 5001 and again["kazan-hq1"][0].kind == "real"
    assert (
        stale["kazan-hq1"][0].night_rub == 5001 and after == 2
    )  # old price shown, new one fetched behind it
    assert nothing == {}  # a failed provider gives no offers, and nothing is cached


def hotel_tools(state, sessionmaker) -> ToolRegistry:  # noqa: F811
    return ToolRegistry(plan_tools(state, sessionmaker, flights=TICKETS))


def test_should_show_more_hotels_with_filters(sessionmaker):  # noqa: F811
    state = TripState(COUPLE)
    registry = hotel_tools(state, sessionmaker)

    shown = call(registry, "search_hotels", {"place": "kazan", "sort": "price", "limit": 4})
    central = call(registry, "search_hotels", {"place": "Казань", "near_centre": True})

    event = shown.event
    assert event["type"] == "hotel_options" and event["place"] == "Казань" and event["nights"] == 7
    totals = [h["total_rub"] for h in event["hotels"]]
    assert len(totals) == 4 and totals == sorted(totals)
    assert all(h["real"] and h["price_estimate"] and not h["terms_known"] for h in event["hotels"])
    assert all(h["area"] == "в центре" or "км" in h["area"] for h in central.event["hotels"])
    assert all(
        h["area"] == "в центре" or h["area"].startswith(("1,", "2,0")) for h in central.event["hotels"]
    )
    assert "build_trip" in json.loads(shown.content)["note"]


def test_should_refuse_hotels_before_the_cards_and_unknown_places(sessionmaker):  # noqa: F811
    fresh = TripState(merge(TripBrief(), BriefPatch(month=11)))
    assert (
        "ask_user"
        in json.loads(call(hotel_tools(fresh, sessionmaker), "search_hotels", {"place": "kazan"}).content)[
            "error"
        ]
    )
    unknown = call(hotel_tools(TripState(COUPLE), sessionmaker), "search_hotels", {"place": "Нигдебург"})
    assert "Unknown place" in json.loads(unknown.content)["error"]


def test_should_build_the_trip_with_the_hotel_the_user_named(sessionmaker):  # noqa: F811
    state = TripState(COUPLE)
    registry = ToolRegistry(plan_tools(state, sessionmaker, flights=TICKETS))
    options = call(registry, "search_hotels", {"place": "antalya", "sort": "stars"}).event["hotels"]
    wanted = options[-1]["name"]

    built = json.loads(
        call(registry, "build_trip", {"id": "antalya", "hotels": [f"отель «{wanted}»"]}).content
    )

    assert built["stops"][0]["hotel"]["name"] == wanted
