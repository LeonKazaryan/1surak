"""Multi-city plans: fixed and best order, legs without prices, trains, dates across months."""

import asyncio
from datetime import date

import pytest
from pydantic import ValidationError

from app.catalog.catalog import load_catalog
from app.flights import city
from app.flights.client import RouteFlights, Ticket
from app.flights.network import Network
from app.flights.planner import Request, Stop, best_ticket, plan, resolve_stop
from app.flights.tools import PlanArgs, flight_tools

CATALOG = load_catalog()


def ticket(price: int, transfers: int = 0, minutes: int = 180, airline: str = "SU") -> Ticket:
    return Ticket("A", "B", airline, "1", "2026-11-12T05:00:00+03:00", price, transfers, minutes, "/x")


def route(price: int, transfers: int = 0, minutes: int = 180) -> RouteFlights:
    t = ticket(price, transfers, minutes)
    return RouteFlights(cheapest=t, direct=t if transfers == 0 else None, fastest=t)


class FakeFlights:
    def __init__(self, prices: dict[tuple[str, str], int], month_prices: dict | None = None):
        self.prices = prices
        self.month_prices = month_prices or {}
        self.calls: list[tuple[str, int | None, tuple[str, ...]]] = []

    async def route(self, origin, destination, month=None):
        return (await self.routes(origin, [destination], month))[destination]

    async def routes(self, origin, destinations, month):
        self.calls.append((origin, month, tuple(destinations)))
        found = {}
        for d in destinations:
            price = self.month_prices.get((origin, d, month), self.prices.get((origin, d)))
            found[d] = route(price) if price else None
        return found


NET = Network(
    {"MOW": {"IST": "TK", "AYT": "SU"}, "IST": {"AYT": "TK"}},
    {c: city(c) for c in ("MOW", "IST", "AYT", "TBS", "HKT")},
)
HOME = Stop.of_city(city("MOW"))


def stops(*names: str) -> tuple[Stop, ...]:
    return tuple(resolve_stop(n, CATALOG) for n in names)


def run(request: Request, flights) -> list:
    return asyncio.run(plan(request, flights, NET))


def test_should_resolve_stops_from_the_catalogue_and_the_city_list():
    assert resolve_stop("Стамбул", CATALOG).code == "IST"
    assert resolve_stop("PEK", CATALOG).code == "BJS"
    assert resolve_stop("Тбилиси", CATALOG).code == "TBS"
    suzdal = resolve_stop("Суздаль", CATALOG)
    assert suzdal.code is None and suzdal.train_min == 150
    assert resolve_stop("Нигдебург", CATALOG) is None


def test_should_price_every_leg_of_a_fixed_order():
    flights = FakeFlights({("MOW", "IST"): 10_000, ("IST", "AYT"): 3_000, ("AYT", "MOW"): 9_000})

    [best] = run(Request(HOME, stops("Стамбул", "Анталья"), month=11), flights)

    view = best.view()
    assert view["order"] == ["Стамбул", "Анталья"] and view["total_price_rub"] == 22_000
    assert [leg["to"] for leg in view["legs"]] == ["Стамбул", "Анталья", "Москва"]
    assert view["unpriced_legs"] == 0 and view["impossible_legs"] == []
    # one call per departure city and month; later legs also look at next month in case the trip spills over
    assert sorted((o, m) for o, m, _ in flights.calls) == [
        ("AYT", 11),
        ("AYT", 12),
        ("IST", 11),
        ("IST", 12),
        ("MOW", 11),
    ]


def test_should_find_the_cheapest_order():
    prices = {
        ("MOW", "IST"): 10_000,
        ("MOW", "TBS"): 8_000,
        ("IST", "TBS"): 4_000,
        ("TBS", "IST"): 30_000,
        ("TBS", "MOW"): 9_000,
        ("IST", "MOW"): 9_000,
    }
    plans = run(Request(HOME, stops("Стамбул", "Тбилиси"), order_fixed=False, month=11), FakeFlights(prices))

    assert [p.view()["order"] for p in plans] == [["Стамбул", "Тбилиси"], ["Тбилиси", "Стамбул"]]
    assert plans[0].view()["total_price_rub"] == 23_000


def test_should_fall_back_to_the_route_map_without_a_price():
    [best] = run(
        Request(HOME, stops("Стамбул", "Пхукет"), return_home=False, month=11),
        FakeFlights({("MOW", "IST"): 10_000}),
    )

    first, second = best.view()["legs"]
    assert first["ticket"]["price_rub"] == 10_000
    assert second["ticket"] is None and second["direct_on_map"] is False and second["est_hours"] > 10
    assert best.view()["unpriced_legs"] == 1 and best.view()["total_price_rub"] == 10_000


def test_should_go_by_train_where_there_is_no_airport():
    [best] = run(Request(HOME, stops("Суздаль")), FakeFlights({}))

    legs = best.view()["legs"]
    assert [leg["mode"] for leg in legs] == ["train", "train"] and legs[0]["est_hours"] == 2.5
    assert best.possible

    [stuck] = run(Request(Stop.of_city(city("IST")), stops("Суздаль")), FakeFlights({}))
    assert not stuck.possible and stuck.view()["impossible_legs"] == [
        "Стамбул → Суздаль",
        "Суздаль → Стамбул",
    ]


def test_should_price_each_leg_in_the_month_it_flies():
    flights = FakeFlights({}, {("MOW", "IST", 11): 10_000, ("IST", "MOW", 12): 7_000})
    request = Request(HOME, stops("Стамбул"), date_from=date(2026, 11, 25), nights=(10,))

    [best] = run(request, flights)

    legs = best.view()["legs"]
    assert [leg["date"] for leg in legs] == ["2026-11-25", "2026-12-05"]
    assert best.view()["total_price_rub"] == 17_000


def test_should_weigh_price_against_time_by_preference():
    slow, fast = ticket(10_000, transfers=2, minutes=900), ticket(14_000, minutes=200)
    found = RouteFlights(cheapest=slow, direct=fast, fastest=fast)

    assert best_ticket(found, "cheapest") is slow
    assert best_ticket(found, "balanced") is fast


def test_should_cap_the_open_order_and_report_unknown_cities():
    with pytest.raises(ValidationError):
        PlanArgs(stops=["a", "b", "c", "d", "e", "f"], order_fixed=False)

    tool = next(t for t in flight_tools(FakeFlights({})) if t.name == "plan_route")
    result = asyncio.run(tool.handler(PlanArgs(stops=["Стамбул", "Нигдебург"])))
    assert result == {"error": "Unknown city: Нигдебург"}

    reply = asyncio.run(tool.handler(PlanArgs(stops=["Стамбул"], month=11)))
    ok = reply.result
    assert ok["from"] == "Москва" and ok["plans"][0]["order"] == ["Стамбул"]
    # the id that makes it a whole trip, when the user asks for one
    assert ok["plans"][0]["trip_id"] == load_catalog().find("Стамбул").id and "build_trip" in ok["next"]
    assert tool.preview(ok).startswith("Москва → Стамбул → Москва")
    # the plan is also drawn as a card, and the agent's turn goes on
    assert reply.event["type"] == "flight_plan" and not reply.ends_turn
    [card] = reply.event["plans"]
    assert card["name"] == "Москва → Стамбул → Москва" and card["best"] is True
