"""Smarter ways for a bad flight: home from Samarkand by train to Tashkent and a direct flight, not two transfers."""

import asyncio
from datetime import date

from app.flights import RouteFlights, Ticket
from app.flights.dictionary import city
from app.flights.network import network
from app.ground import GroundOption, GroundRoute
from app.ground import configure as configure_ground
from app.trip.legs import Leg
from app.trip.routes import chain_dates
from app.trip.smart import _checked, better_way, fit_rides

SKD, TAS, NQZ = city("SKD"), city("TAS"), city("NQZ")
DAY = date(2027, 5, 20)


def fare(price: int, transfers: int, minutes: int, when: str = "2027-05-20T14:30:00+05:00") -> RouteFlights:
    ticket = Ticket("A", "B", "KC", "1", when, price, transfers, minutes, "/t")
    return RouteFlights(
        cheapest=ticket, direct=ticket if not transfers else None, fastest=ticket, by_day=(ticket,)
    )


class PairFlights:
    """Fares by (origin, destination): the conftest fake only knows destinations."""

    def __init__(self, table: dict[tuple[str, str], RouteFlights]):
        self.table = table

    async def route(self, origin, destination, month=None):
        return self.table.get((origin, destination))

    async def routes(self, origin, destinations, month):
        return {d: self.table.get((origin, d)) for d in destinations}


class Trains:
    def __init__(self, found: dict[tuple[str, str], GroundRoute]):
        self.found = found

    async def route(self, origin, destination, day=None):
        return self.found.get((origin.code, destination.code))


AFROSIYOB = GroundRoute(
    (GroundOption("train", "tutu", "Афросиаб 768Ф", "16:49", "19:04", 135, 2986, "сидячий", "/t"),)
)


def bad_flight_home() -> Leg:
    found = fare(46_864, 2, 570)
    return Leg(
        "Самарканд", "Астана", 1700, "flight", 9.5, ("SKD", "NQZ"), flights=found, ticket=found.cheapest
    )


def test_should_go_home_by_train_to_a_neighbouring_airport_when_the_direct_flight_is_bad():
    configure_ground(Trains({("SKD", "TAS"): AFROSIYOB}))
    flights = PairFlights({("TAS", "NQZ"): fare(8_625, 0, 180)})

    way = asyncio.run(better_way(bad_flight_home(), SKD, NQZ, 5, DAY, flights, network()))

    assert way.via == "Ташкент"
    assert [p.mode for p in way.parts] == ["ground", "flight"]
    assert way.parts[0].ground.best.name == "Афросиаб 768Ф"
    assert way.price_rub == 2_986 + 8_625
    assert way.instead == {"price_rub": 46_864, "transfers": 2, "hours": 9.5, "airline": "Air Astana"}


def test_should_keep_a_good_direct_flight():
    direct = fare(9_000, 0, 200)
    leg = Leg(
        "Самарканд", "Астана", 1700, "flight", 3.5, ("SKD", "NQZ"), flights=direct, ticket=direct.cheapest
    )

    assert asyncio.run(better_way(leg, SKD, NQZ, 5, DAY, PairFlights({}), network())) is None


def test_should_not_replace_a_ticket_for_a_small_saving():
    configure_ground(Trains({("SKD", "TAS"): AFROSIYOB}))
    nearly = fare(13_000, 1, 300)
    leg = Leg(
        "Самарканд", "Астана", 1700, "flight", 5, ("SKD", "NQZ"), flights=nearly, ticket=nearly.cheapest
    )

    way = asyncio.run(
        better_way(leg, SKD, NQZ, 5, DAY, PairFlights({("TAS", "NQZ"): fare(11_500, 0, 180)}), network())
    )

    assert way is None  # a train and a change for a few thousand is not a clear win


def test_should_not_rely_on_an_unchecked_road_across_a_border():
    abroad = Leg("Шымкент", "Самарканд", 400, "ground", 8, ("CIT", "SKD"))
    at_home = Leg("Самарканд", "Ташкент", 270, "ground", 5, ("SKD", "TAS"))

    assert not asyncio.run(_checked([abroad], DAY))  # nothing found and a border on the way
    assert asyncio.run(_checked([at_home], DAY))  # one country: the estimate will do


def test_should_chain_the_second_plane_of_a_connection_three_to_thirty_hours_later():
    first = fare(5_000, 0, 240, "2027-05-10T10:00:00+05:00")  # lands 14:00
    too_soon = Ticket("A", "B", "KC", "2", "2027-05-10T15:00:00+05:00", 4_000, 0, 120, "/t")
    next_morning = Ticket("A", "B", "KC", "3", "2027-05-11T09:00:00+05:00", 6_000, 0, 120, "/t")
    second = RouteFlights(
        cheapest=too_soon, direct=too_soon, fastest=too_soon, by_day=(too_soon, next_morning)
    )
    leg = Leg("A", "B", 2000, "flight", 6, parts=[
        Leg("A", "H", 1000, "flight", 4, flights=first, ticket=first.cheapest),
        Leg("H", "B", 1000, "flight", 2, flights=second),
    ])  # fmt: skip

    assert chain_dates([leg], [], start_at_home=True)
    assert leg.parts[1].ticket is next_morning  # 1 h after landing is too tight on separate tickets


def test_should_take_the_train_that_leaves_after_the_plane_lands():
    morning = GroundOption("train", "tutu", "Поезд 716Ф", "06:58", "10:00", 180, 1_867, "плацкарт", "/t")
    afternoon = GroundOption("train", "tutu", "Афросиаб 766Ф", "15:28", "17:40", 132, 2_986, "сидячий", "/t")
    flight = fare(8_224, 0, 90, "2027-05-18T10:45:00+05:00")  # Almaty 10:45 > Tashkent 12:15
    plane = Leg(
        "Алматы", "Ташкент", 680, "flight", 1.5, ("ALA", "TAS"), flights=flight, ticket=flight.cheapest
    )
    train = Leg(
        "Ташкент", "Самарканд", 270, "ground", 3, ("TAS", "SKD"), ground=GroundRoute((morning, afternoon))
    )

    fit_rides([plane, train])

    assert train.ground.best.name == "Афросиаб 766Ф"  # tomorrow's 06:58 would mean a night at the station
    assert train.ground.wait_min == 15 * 60 + 28 - (12 * 60 + 15 + 90)
    assert train.ground.view()["wait_hours"] == 1.5


def test_should_take_the_train_that_arrives_in_time_for_the_plane():
    early = GroundOption("train", "tutu", "Поезд 123Ф", "22:33", "02:33", 240, 1_387, "плацкарт", "/t")
    late = GroundOption("train", "tutu", "Афросиаб 768Ф", "16:49", "19:04", 135, 2_986, "сидячий", "/t")
    flight = fare(7_471, 0, 180, "2027-05-21T15:10:00+05:00")
    train = Leg("Самарканд", "Ташкент", 270, "ground", 4, ("SKD", "TAS"), ground=GroundRoute((early, late)))
    plane = Leg(
        "Ташкент", "Астана", 1300, "flight", 3, ("TAS", "NQZ"), flights=flight, ticket=flight.cheapest
    )

    fit_rides([train, plane])

    assert (
        train.ground.best.name == "Поезд 123Ф"
    )  # the night train is in by 02:33; 19:04 misses the 15:10 plane


def calendar(*fares: tuple[str, int]) -> RouteFlights:
    tickets = tuple(
        Ticket("A", "B", "KC", "1", f"2027-{day}T10:00:00+05:00", price, 0, 120, "/t") for day, price in fares
    )
    return RouteFlights(
        cheapest=min(tickets, key=lambda t: t.price), direct=tickets[0], fastest=tickets[0], by_day=tickets
    )


def test_should_keep_the_dates_near_the_plan_when_no_chain_fits():
    out = calendar(("05-28", 12_761))  # seven months ahead, one fare is all Aviasales has
    home = calendar(("06-09", 6_245), ("06-22", 2_602))
    legs = [
        Leg("Астана", "Самарканд", 1700, "flight", 3, ("NQZ", "SKD"), flights=out),
        Leg("Самарканд", "Бухара", 270, "ground", 3, ("SKD", "BHK")),
        Leg("Бухара", "Астана", 1900, "flight", 3, ("BHK", "NQZ"), flights=home),
    ]

    assert chain_dates(legs, [4, 4]) is False
    assert legs[2].ticket.day == date(2027, 6, 9)  # four days late, not the cheapest one seventeen days late
