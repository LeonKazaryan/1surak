"""The departure city: named in the chat, picked in the browser, or only guessed, and dates that chain."""

import asyncio
from datetime import date

from app.catalog.catalog import load_catalog
from app.chats.service import pick_origin
from app.flights import city, current_origin
from app.flights.client import RouteFlights, Ticket
from app.flights.dictionary import find_city
from app.flights.network import Network
from app.flights.planner import Request, Stop, plan, resolve_stop
from app.money import current_currency
from app.tools import ToolReply
from app.trip.brief import BriefPatch, TripBrief, assumptions, chips, merge, missing, prefill
from app.trip.tools import TripState, trip_tools

FULL = {
    "kinds": ["sea"],
    "month": 11,
    "nights_min": 7,
    "nights_max": 7,
    "adults": 2,
    "children": 0,
    "budget_level": 2,
}


def test_should_find_a_city_by_name_or_code():
    assert find_city("Алматы").code == "ALA"
    assert find_city("астаны").code == "NQZ"  # «из Астаны»
    assert find_city("svo").code == "MOW"
    assert find_city("Нигдебург") is None and find_city("") is None


def test_should_keep_the_city_the_user_named():
    token = current_origin.set("MOW")
    try:
        brief = merge(TripBrief(), BriefPatch(origin="Алматы"))
        assert brief.origin_code == "ALA" and brief.origin == "Алматы" and brief.origin_over == "MOW"
        assert "Из Алматы" in chips(brief)
        unknown = merge(brief, BriefPatch(origin="Нигдебург"))
        assert unknown.origin_code == "ALA"  # a name we cannot place does not move the trip
    finally:
        current_origin.reset(token)


def test_should_keep_asking_where_from_only_while_the_city_is_a_fallback():
    token = current_origin.set("MOW")
    try:
        guessed = TripBrief(**FULL, origin_guess=True, asked=True)
        assert missing(guessed) == ["origin"]  # still unknown after the cards: it stays a gap
        assert assumptions(guessed) == ["вылет из Москвы"]
        assert missing(TripBrief(**FULL, asked=True)) == []  # detected by IP
        assert missing(TripBrief(**FULL, origin_guess=True, origin_code="ALA", asked=True)) == []
        assert missing(TripBrief(**FULL))[0] == "origin"  # a new trip always confirms the city
        assert prefill(TripBrief())["origin"] == {"code": "MOW", "name": "Москва"}
    finally:
        current_origin.reset(token)


def test_should_pick_the_city_of_the_turn():
    named = TripBrief(origin_code="ALA", origin_over="MOW")

    # the browser still sends its old guess: the city named in the chat wins
    assert pick_origin(named, "MOW", True)[1] == "ALA"
    assert pick_origin(named, "ALA", True)[1] == "ALA"
    assert pick_origin(named, None, True)[1] == "ALA"
    # the user picked another city in the browser after that: it becomes the chat's city
    moved, code = pick_origin(named, "LED", True)
    assert code == "LED" and moved.origin_code == "LED"
    # nothing named and the browser could not detect: the fallback is a guess the agent asks about
    guess, code = pick_origin(TripBrief(), None, False)
    assert code == "MOW" and guess.origin_guess is True
    assert pick_origin(TripBrief(), "KZN", True)[0].origin_guess is False


def test_should_search_from_the_city_named_in_the_message():
    async def run():
        state = TripState(TripBrief())
        update = next(t for t in trip_tools(state, None) if t.name == "update_trip_brief")
        origin, currency = current_origin.set("MOW"), current_currency.set(current_currency.get())
        try:
            reply = await update.handler(update.args(origin="Астана", kinds=["sea"]))
            return reply, current_origin.get(), current_currency.get().code, state.brief
        finally:
            current_origin.reset(origin)
            current_currency.reset(currency)

    reply, origin, currency, brief = asyncio.run(run())

    assert isinstance(reply, ToolReply) and reply.event == {"type": "origin", "code": "NQZ", "name": "Астана"}
    assert origin == "NQZ" and currency == "KZT" and brief.origin_code == "NQZ"
    assert "origin_changed" in reply.result


def ticket(price: int, day: str) -> Ticket:
    return Ticket("A", "B", "SU", "1", f"{day}T10:00:00+03:00", price, 0, 120, "/x")


def calendar(*tickets: Ticket) -> RouteFlights:
    cheapest = min(tickets, key=lambda t: t.price)
    return RouteFlights(
        cheapest, cheapest, cheapest, by_day=tuple(sorted(tickets, key=lambda t: t.departure_at))
    )


class MonthFlights:
    def __init__(self, table):
        self.table = table

    async def routes(self, origin, destinations, month):
        return {d: self.table.get((origin, d, month)) for d in destinations}


NET = Network({}, {c: city(c) for c in ("MOW", "IST", "AYT")})
HOME = Stop.of_city(city("MOW"))
STOPS = tuple(resolve_stop(n, load_catalog()) for n in ("Стамбул", "Анталья"))


def test_should_chain_the_dates_of_a_trip_with_only_a_month():
    # each leg alone is cheapest on a day that comes before the leg it follows
    flights = MonthFlights(
        {
            ("MOW", "IST", 11): calendar(ticket(9_000, "2026-11-20"), ticket(10_000, "2026-11-05")),
            ("IST", "AYT", 11): calendar(ticket(2_000, "2026-11-02"), ticket(3_000, "2026-11-08")),
            ("AYT", "MOW", 11): calendar(ticket(7_000, "2026-11-01"), ticket(8_000, "2026-11-13")),
        }
    )
    [best] = asyncio.run(plan(Request(HOME, STOPS, month=11, nights=(3, 5)), flights, NET))

    view = best.view()
    assert view["dates_chained"] is True
    assert [leg["date"] for leg in view["legs"]] == ["2026-11-05", "2026-11-08", "2026-11-13"]
    assert view["total_price_rub"] == 21_000


def test_should_let_a_trip_spill_into_next_month():
    flights = MonthFlights(
        {
            ("MOW", "IST", 11): calendar(ticket(9_000, "2026-11-28")),
            ("IST", "AYT", 12): calendar(ticket(2_000, "2026-12-01")),
            ("AYT", "MOW", 12): calendar(ticket(7_000, "2026-12-04")),
        }
    )
    [best] = asyncio.run(plan(Request(HOME, STOPS, month=11), flights, NET))

    assert best.dates_chained and [leg.day for leg in best.legs] == [
        date(2026, 11, 28),
        date(2026, 12, 1),
        date(2026, 12, 4),
    ]


def test_should_say_when_the_dates_cannot_chain():
    flights = MonthFlights(
        {
            ("MOW", "IST", 11): calendar(ticket(9_000, "2026-11-20")),
            ("IST", "AYT", 11): calendar(ticket(2_000, "2026-11-02")),
        }
    )
    [best] = asyncio.run(plan(Request(HOME, STOPS, return_home=False, month=11), flights, NET))

    assert best.view()["dates_chained"] is False
    assert best.view()["total_price_rub"] == 11_000  # each leg keeps its own cheapest ticket


def test_should_hand_the_users_own_cities_to_plan_route():
    from app.trip.brief import search_hint

    catalog = load_catalog()
    named = TripBrief(destination="Ташкент и Бишкек", multi_city=True, month=12)
    vague = TripBrief(destination="Кавказ", multi_city=True, month=12)

    assert search_hint(named, catalog)["plan_route"] == {"stops": ["Ташкент", "Бишкек"]}
    assert "multi_city" not in search_hint(named, catalog)
    assert search_hint(vague, catalog)["multi_city"] is True and "plan_route" not in search_hint(
        vague, catalog
    )


def test_should_not_announce_a_city_the_turn_already_flies_from():
    async def run():
        state = TripState(TripBrief())
        update = next(t for t in trip_tools(state, None) if t.name == "update_trip_brief")
        token = current_origin.set("MOW")
        try:
            return await update.handler(update.args(origin="Москва"))
        finally:
            current_origin.reset(token)

    result = asyncio.run(run())

    assert isinstance(result, dict) and "origin_changed" not in result  # no event, no switch


def test_should_not_take_a_price_per_night_for_the_trip_budget():
    from app.trip.brief import per_night_budget

    hotel = BriefPatch(budget_total=8000, wishes=["отель в центре", "до 8 000 ₽ за ночь"])
    trip = BriefPatch(budget_total=150000, wishes=["отель в центре"])

    assert per_night_budget(hotel) and not per_night_budget(trip)

    async def run():
        state = TripState(TripBrief())
        update = next(t for t in trip_tools(state, None) if t.name == "update_trip_brief")
        result = await update.handler(
            update.args(destination="Казань", budget_total=8000, wishes=hotel.wishes)
        )
        return result, state.brief

    result, brief = asyncio.run(run())
    assert brief.budget_total is None and "до 8 000 ₽ за ночь" in brief.wishes
    assert "ask_user" in result["next"]  # a new trip: the cards come before any search
