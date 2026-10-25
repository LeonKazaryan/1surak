"""Per-day calendars, hubs from the route map, connections that can be flown, and the popular-fare refresher."""

import asyncio
from datetime import UTC, date, datetime, timedelta

import httpx

from app.flights import city
from app.flights.client import RouteFlights, Ticket, TravelpayoutsFlights, summarize
from app.flights.connections import connect, hubs
from app.flights.freshness import Popularity
from app.flights.network import Network
from app.flights.planner import Request, Stop, plan
from tests.test_flights import ROWS

NOW = datetime(2026, 10, 25, 12, tzinfo=UTC)
CODES = ("MOW", "IST", "BJV", "DXB", "ALA")
NET = Network(
    {"MOW": {"IST": "TK", "DXB": "EK", "BJV": "SU"}, "IST": {"BJV": "TK"}, "DXB": {"BJV": "FZ"}},
    {c: city(c) for c in CODES},
)


def ticket(price: int, departs: str, minutes: int = 180, transfers: int = 0) -> Ticket:
    return Ticket("A", "B", "TK", "1", departs, price, transfers, minutes, "/x")


def calendar(*tickets: Ticket) -> RouteFlights:
    cheapest = min(tickets, key=lambda t: t.price)
    return RouteFlights(
        cheapest, cheapest, cheapest, by_day=tuple(sorted(tickets, key=lambda t: t.departure_at))
    )


def by_price(price, minutes, transfers):
    return price


def test_should_keep_the_cheapest_ticket_of_every_day():
    rows = [
        *ROWS,
        {**ROWS[0], "price": 8000, "departure_at": "2026-11-12T22:00:00+06:00", "link": "/c"},
    ]
    found = summarize(rows)

    assert [(t.day, t.price) for t in found.by_day] == [
        (date(2026, 11, 12), 8000),
        (date(2026, 11, 13), 10558),
    ]
    assert found.on(date(2026, 11, 13)).price == 10558 and found.on(date(2026, 11, 1)) is None
    # 05:05 at +06:00 plus 345 min, compared across zones
    assert found.on(date(2026, 11, 13)).arrives == datetime(2026, 11, 13, 4, 50, tzinfo=UTC)


def test_should_pick_hubs_that_add_little_distance():
    assert hubs(NET, "MOW", "BJV") == ["IST"]  # Dubai is far out of the way
    assert hubs(NET, "SVO", "BJV") == ["IST"]
    assert hubs(NET, "MOW", "ALA") == [] and hubs(NET, "MOW", "MOW") == []


def test_should_only_connect_flights_that_can_be_flown_in_a_row():
    hub = city("IST")
    first = calendar(ticket(5000, "2026-11-10T08:00:00+03:00"), ticket(4000, "2026-11-20T08:00:00+03:00"))
    second = calendar(
        ticket(3000, "2026-11-10T12:00:00+03:00"),  # 1 h after landing: too tight for separate tickets
        ticket(3500, "2026-11-10T16:00:00+03:00"),
        ticket(1000, "2026-11-25T10:00:00+03:00"),  # cheap, but five days later
    )

    found = connect(hub, first, second, by_price)

    assert found.price == 8500 and found.layover == timedelta(hours=5) and found.transfers == 1
    assert found.view()["via"] == "Стамбул" and found.view()["separate_tickets"] is True
    assert connect(hub, first, second, by_price, day=date(2026, 11, 20)) is None


class CalendarFlights:
    def __init__(self, routes: dict[tuple[str, str], RouteFlights]):
        self.routes_by_pair = routes

    async def routes(self, origin, destinations, month):
        return {d: self.routes_by_pair.get((origin, d)) for d in destinations}


HOME = Stop.of_city(city("MOW"))
BODRUM = Stop.of_city(city("BJV"))


def test_should_offer_a_hub_when_it_saves_enough():
    flights = CalendarFlights(
        {
            ("MOW", "BJV"): calendar(ticket(20_000, "2026-11-10T09:00:00+03:00")),
            ("MOW", "IST"): calendar(ticket(6_000, "2026-11-10T08:00:00+03:00")),
            ("IST", "BJV"): calendar(ticket(4_000, "2026-11-10T16:00:00+03:00", minutes=70)),
        }
    )
    [best] = asyncio.run(plan(Request(HOME, (BODRUM,), return_home=False, month=11), flights, NET))

    view = best.view()
    leg = view["legs"][0]
    assert leg["ticket"]["price_rub"] == 20_000
    assert leg["cheaper_via"]["via"] == "Стамбул" and leg["cheaper_via"]["saves_rub"] == 10_000
    assert view["total_price_rub"] == 20_000 and view["total_with_connections_rub"] == 10_000


def test_should_not_offer_a_slow_hub_to_someone_in_a_hurry():
    flights = CalendarFlights(
        {
            ("MOW", "BJV"): calendar(ticket(20_000, "2026-11-10T09:00:00+03:00")),
            ("MOW", "IST"): calendar(ticket(6_000, "2026-11-10T08:00:00+03:00")),
            ("IST", "BJV"): calendar(ticket(4_000, "2026-11-10T16:00:00+03:00", minutes=70)),
        }
    )
    request = Request(HOME, (BODRUM,), return_home=False, month=11, preference="fastest")

    [best] = asyncio.run(plan(request, flights, NET))

    assert "cheaper_via" not in best.view()["legs"][0]


def test_should_not_offer_a_hub_for_a_small_saving():
    flights = CalendarFlights(
        {
            ("MOW", "BJV"): calendar(ticket(11_000, "2026-11-10T09:00:00+03:00")),
            ("MOW", "IST"): calendar(ticket(6_000, "2026-11-10T08:00:00+03:00")),
            ("IST", "BJV"): calendar(ticket(4_000, "2026-11-10T16:00:00+03:00", minutes=70)),
        }
    )
    [best] = asyncio.run(plan(Request(HOME, (BODRUM,), return_home=False, month=11), flights, NET))

    assert "cheaper_via" not in best.view()["legs"][0] and "total_with_connections_rub" not in best.view()


def test_should_price_a_dated_leg_on_its_day_when_the_calendar_has_it():
    flights = CalendarFlights(
        {
            ("MOW", "BJV"): calendar(
                ticket(9_000, "2026-11-03T09:00:00+03:00"), ticket(12_000, "2026-11-15T09:00:00+03:00")
            )
        }
    )
    request = Request(HOME, (BODRUM,), return_home=False, date_from=date(2026, 11, 15))

    [best] = asyncio.run(plan(request, flights, NET))
    [other_day] = asyncio.run(
        plan(Request(HOME, (BODRUM,), return_home=False, date_from=date(2026, 11, 20)), flights, NET)
    )

    assert (
        best.view()["legs"][0]["ticket"]["price_rub"] == 12_000
        and best.view()["legs"][0]["exact_day"] is True
    )
    assert other_day.view()["legs"][0]["exact_day"] is False  # falls back to the month's best ticket


def test_should_forget_popularity_over_time():
    popular = Popularity()
    for _ in range(4):
        popular.touch("a", NOW)
    popular.touch("b", NOW)

    assert popular.score("a", NOW + timedelta(hours=6)) == 2.0
    assert popular.hottest(["a", "b", "c"], NOW, at_least=1) == ["a", "b"]
    assert popular.hottest(["a", "b"], NOW + timedelta(hours=12), at_least=1.5) == []


def test_should_refresh_popular_fares_before_they_expire():
    asked = []

    def handler(request: httpx.Request) -> httpx.Response:
        asked.append(request.url.params["destination"])
        return httpx.Response(200, json={"data": ROWS})

    clock = [NOW]

    async def run():
        flights = TravelpayoutsFlights(
            "token", httpx.AsyncClient(transport=httpx.MockTransport(handler)), clock=lambda: clock[0]
        )
        for _ in range(3):
            await flights.routes("MOW", ["IST"], 11)  # popular
        await flights.routes("MOW", ["AYT"], 11)  # asked once
        early = await flights.refresh_due(budget=10)
        clock[0] += timedelta(hours=2, minutes=45)  # 15 minutes before the 3 h expiry
        due = await flights.refresh_due(budget=10)
        return early, due

    early, due = asyncio.run(run())

    assert early == 0 and due == 1
    assert asked == ["IST", "AYT", "IST"]
