"""Multi-city routes: which places chain, how they score against interests, how nights and legs work out."""

import asyncio

from app.catalog.catalog import Country, Place
from app.catalog.search import Snapshot
from app.flights import City
from app.trip.routes import RouteQuery, candidate_routes, find_routes, named_route, price_route, split_nights
from tests.conftest import FakeFlights, route

OCT = 10
ARMENIA = Country("AM", "Армения", "visa_free", 180, "")
GEORGIA = Country("GE", "Грузия", "visa_free", 365, "")
TURKEY = Country("TR", "Турция", "visa_free", 60, "")
ASTANA = City("NQZ", "Астана", "Казахстан", 51.15, 71.42, "Астаны")


def place(
    id: str, country: Country, lat: float, lon: float, kinds=("city",), kids="good", airport=None
) -> Place:
    return Place(
        id=id,
        qid=f"Q{id}",
        name=id.title(),
        country=country,
        kinds=tuple(kinds),
        airport=airport,
        lat=lat,
        lon=lon,
        price_level=2,
        kids=kids,
        highlights=("a", "b"),
        watch_out=(),
        train_min=None,
    )


def snap(p: Place, day: float = 20) -> Snapshot:
    return Snapshot(place=p, climate={OCT: {"air_max": day}}, visa_rule=p.country.visa)


YEREVAN = snap(place("yerevan", ARMENIA, 40.18, 44.51, ("city", "mountains"), airport="EVN"))
TBILISI = snap(place("tbilisi", GEORGIA, 41.72, 44.79, ("city",), airport="TBS"))
BATUMI = snap(place("batumi", GEORGIA, 41.64, 41.63, ("sea", "city"), airport="BUS"))
ISTANBUL = snap(place("istanbul", TURKEY, 41.01, 28.98, ("city",), airport="IST"))
WORLD = [YEREVAN, TBILISI, BATUMI, ISTANBUL]


def names(plans) -> list[str]:
    return [p.name for p in plans]


def test_should_chain_only_places_within_reach_and_start_near_home():
    plans = candidate_routes(WORLD, RouteQuery(month=OCT, kinds=["city"], nights=8), ASTANA)

    assert "Tbilisi → Yerevan" in names(plans)  # Tbilisi is closer to Astana, so the trip starts there
    assert "Yerevan → Tbilisi" not in names(plans)
    assert all("Istanbul" not in n or "Batumi" in n for n in names(plans))  # Istanbul only reaches Batumi


def test_should_rank_routes_by_how_they_cover_the_interests():
    plans = candidate_routes(WORLD, RouteQuery(month=OCT, kinds=["city", "mountains"], nights=8), ASTANA)

    assert "Yerevan" in plans[0].name  # the only stop with mountains
    interests = {i["kind"]: i["covered"] for i in plans[0].interests}
    assert interests["city"] and interests["mountains"]
    assert plans[0].match > 0


def test_should_leave_out_places_that_do_not_suit_small_children():
    rough = snap(place("kazbegi", GEORGIA, 42.66, 44.64, ("mountains",), kids="poor"))

    plans = candidate_routes([*WORLD, rough], RouteQuery(month=OCT, with_kids=True, nights=8), ASTANA)

    assert all("Kazbegi" not in n for n in names(plans))


def test_should_keep_at_least_two_nights_per_city():
    assert split_nights(7, [YEREVAN, TBILISI]) == [4, 3]  # the spare night goes to the stop with more to do
    three = candidate_routes(WORLD, RouteQuery(month=OCT, nights=5), ASTANA)
    assert all(len(p.stops) == 2 for p in three)  # 5 nights are not enough for three cities


def test_should_fly_the_long_legs_and_estimate_the_short_hops_by_land():
    flights = FakeFlights({"TBS": route(240, price=30_000), "NQZ": route(250, price=28_000)})
    plan = candidate_routes([YEREVAN, TBILISI], RouteQuery(month=OCT, nights=8), ASTANA)[0]

    asyncio.run(price_route(plan, flights, ASTANA, OCT))

    legs = [(leg.origin, leg.destination, leg.mode) for leg in plan.legs]
    assert legs == [
        ("Астана", "Tbilisi", "flight"),
        ("Tbilisi", "Yerevan", "ground"),
        ("Yerevan", "Астана", "flight"),
    ]
    assert plan.legs[1].view()["estimate"].startswith("по земле")
    assert plan.total_rub == 58_000 and plan.priced


def test_should_not_offer_two_routes_that_are_mostly_the_same_cities():
    plans = asyncio.run(find_routes(WORLD, RouteQuery(month=OCT, nights=9, limit=3), FakeFlights(), ASTANA))

    sets = [{s.place.id for s in p.stops} for p in plans]
    assert len(plans) >= 2
    assert all(len(a & b) / len(a | b) <= 0.5 for i, a in enumerate(sets) for b in sets[i + 1 :])


def test_should_not_send_a_long_hop_by_land_when_a_city_has_no_airport():
    far = snap(
        place("anapa", Country("RU", "Россия", "none", None, ""), 44.89, 37.32, ("sea",))
    )  # no airport

    plans = candidate_routes([YEREVAN, far], RouteQuery(month=OCT, nights=8), ASTANA)

    assert plans == []  # 700 km over the mountains is not a bus ride


def tickets(*days_prices: tuple[str, int]):
    from app.flights import RouteFlights, Ticket

    found = tuple(
        sorted(
            (
                Ticket("A", "B", "SU", "1", f"{day}T10:00:00+03:00", price, 0, 240, "/t")
                for day, price in days_prices
            ),
            key=lambda t: t.price,
        )
    )
    return RouteFlights(cheapest=found[0], direct=found[0], fastest=found[0], by_day=found)


def test_should_pick_tickets_whose_dates_follow_the_nights():
    from app.trip.routes import Leg, chain_dates

    there = Leg(
        "Астана", "Tbilisi", 2500, "flight", 4, flights=tickets(("2026-10-29", 14000), ("2026-10-10", 16000))
    )
    hop = Leg("Tbilisi", "Yerevan", 175, "ground", 3.5)
    back = Leg(
        "Yerevan", "Астана", 2600, "flight", 3, flights=tickets(("2026-10-26", 11000), ("2026-10-19", 12500))
    )

    chained = chain_dates([there, hop, back], [5, 4])

    assert chained
    # the cheapest outbound (29 Oct) has no return 9 days later, so the 10 Oct + 19 Oct pair wins
    assert (there.ticket.day.isoformat(), back.ticket.day.isoformat()) == ("2026-10-10", "2026-10-19")


def test_should_say_so_when_no_dates_chain():
    from app.trip.routes import Leg, chain_dates

    there = Leg("Астана", "Tbilisi", 2500, "flight", 4, flights=tickets(("2026-10-29", 14000)))
    back = Leg("Yerevan", "Астана", 2600, "flight", 3, flights=tickets(("2026-10-26", 11000)))

    assert not chain_dates([there, back], [5])
    assert there.ticket.price == 14000 and back.ticket.price == 11000  # the cheapest, flagged as not chained


def test_should_find_the_way_back_in_the_next_month_when_the_trip_crosses_it():
    class ByMonth:
        async def route(self, origin, destination, month=None):
            if destination == "TBS" and month == OCT:
                return tickets(("2026-10-27", 14000))
            if destination == "NQZ" and month == OCT + 1:
                return tickets(("2026-11-05", 12000))
            return None

    plan = candidate_routes([YEREVAN, TBILISI], RouteQuery(month=OCT, nights=9), ASTANA)[0]
    asyncio.run(price_route(plan, ByMonth(), ASTANA, OCT))

    assert plan.dates_chained  # 27 Oct + 9 nights = 5 Nov, found in November
    assert plan.total_rub == 26_000


def test_should_leave_on_the_day_the_user_named():
    from datetime import date

    from app.trip.routes import Leg, chain_dates

    there = Leg(
        "Астана", "Tbilisi", 2500, "flight", 4, flights=tickets(("2026-10-10", 14000), ("2026-10-20", 19000))
    )
    back = Leg(
        "Tbilisi", "Астана", 2600, "flight", 3, flights=tickets(("2026-10-17", 11000), ("2026-10-27", 12500))
    )

    chained = chain_dates([there, back], [7], start=date(2026, 10, 20))

    assert chained
    assert (there.ticket.day.isoformat(), back.ticket.day.isoformat()) == ("2026-10-20", "2026-10-27")


def line(n: int, country: Country = GEORGIA) -> list:
    """n cities in a row 200 km apart, all by land."""
    return [snap(place(f"c{i}", country, 41.0, 40.0 + 2.4 * i, ("city",))) for i in range(n)]


def test_should_grow_a_tour_of_five_cities_without_zigzags():
    plans = candidate_routes(line(5), RouteQuery(month=OCT, nights=14, min_stops=5), ASTANA)

    assert plans and all(len(p.stops) == 5 for p in plans)
    order = [s.place.id for s in plans[0].stops]
    assert order in (["c0", "c1", "c2", "c3", "c4"], ["c4", "c3", "c2", "c1", "c0"])


def test_should_cap_a_tour_at_two_nights_a_city_and_seven_cities():
    squeezed = candidate_routes(line(6), RouteQuery(month=OCT, nights=7, min_stops=5), ASTANA)
    assert squeezed and max(len(p.stops) for p in squeezed) == 3  # 7 nights hold 3 cities, not the 5 asked
    many = candidate_routes(line(9), RouteQuery(month=OCT, nights=30, min_stops=7), ASTANA)
    assert many and max(len(p.stops) for p in many) == 7


def test_should_not_cross_a_border_by_a_long_road_or_fly_where_nothing_flies():
    erevan = snap(place("erevan", ARMENIA, 40.18, 44.51, ("city",), airport="EVN"))
    baku = snap(
        place("baku", Country("AZ", "Азербайджан", "evisa", 30, ""), 40.41, 49.87, ("city",), airport="GYD")
    )

    assert candidate_routes([erevan, baku], RouteQuery(month=OCT, nights=8), ASTANA) == []


def test_should_build_the_users_own_cities_in_the_order_with_the_cheaper_way_home():
    from tests.test_smart import PairFlights, fare

    flights = PairFlights(
        {
            ("NQZ", "IST"): fare(20_000, 0, 420, "2026-10-05T08:00:00+05:00"),
            ("IST", "BUS"): fare(5_000, 0, 120, "2026-10-09T08:00:00+03:00"),
            ("BUS", "NQZ"): fare(80_000, 2, 1_400, "2026-10-13T08:00:00+04:00"),  # home from Batumi is dear
            ("NQZ", "BUS"): fare(30_000, 0, 360, "2026-10-05T08:00:00+05:00"),
            ("BUS", "IST"): fare(5_000, 0, 120, "2026-10-09T08:00:00+04:00"),
            ("IST", "NQZ"): fare(20_000, 0, 400, "2026-10-13T08:00:00+03:00"),
        }
    )

    plan = asyncio.run(named_route([ISTANBUL, BATUMI], RouteQuery(month=OCT, nights=8), flights, ASTANA))

    assert plan.name == "Batumi → Istanbul" and plan.total_rub == 55_000


def test_should_keep_the_users_order_when_they_gave_it():
    query = RouteQuery(month=OCT, nights=8, order_fixed=True)

    plan = asyncio.run(named_route([ISTANBUL, BATUMI], query, FakeFlights(), ASTANA))

    assert plan.name == "Istanbul → Batumi"
