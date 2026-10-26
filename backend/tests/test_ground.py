"""Trains and buses: what the timetables answer, how it is read, and that a failing source never breaks a route."""

import asyncio
from datetime import date

import httpx

from app.flights.dictionary import City
from app.ground import GroundOption, GroundRoute, GroundTransport
from app.ground.flixbus import FlixBuses, rides_from
from app.ground.tutu import TutuTrains, trains_from

SAMARKAND = City("SKD", "Самарканд", "Узбекистан", 39.65, 66.96)
TASHKENT = City("TAS", "Ташкент", "Узбекистан", 41.3, 69.24)
ISTANBUL = City("IST", "Стамбул", "Турция", 41.01, 28.98)
ANTALYA = City("AYT", "Анталья", "Турция", 36.9, 30.71)

AFROSIYOB = {
    "name": "Афросиаб",
    "trainNumber": "768Ф",
    "departureTime": "16:49:00",
    "arrivalTime": "19:04:00",
    "travelTimeInSeconds": "8100",
    "categories": [{"type": "sedentary", "price": 2986}, {"type": "coupe", "price": 0}],
}
NIGHT_TRAIN = {
    "name": "",
    "trainNumber": "123Ф",
    "departureTime": "22:33:00",
    "arrivalTime": "02:33:00",
    "travelTimeInSeconds": "14400",
    "categories": [{"type": "plazcard", "price": 1387}],
}


def test_should_read_a_timetable_with_the_cheapest_fare_of_each_train():
    trains = trains_from([AFROSIYOB, NIGHT_TRAIN], "https://www.tutu.ru/poezda/rasp_d.php?nnst1=1&nnst2=2")

    assert [(t.name, t.departs, t.minutes, t.price_rub, t.fare) for t in trains] == [
        ("Афросиаб 768Ф", "16:49", 135, 2986, "сидячий"),
        ("Поезд 123Ф", "22:33", 240, 1387, "плацкарт"),
    ]
    route = GroundRoute(tuple(trains))
    assert route.cheapest.name == "Поезд 123Ф" and route.fastest.name == "Афросиаб 768Ф"
    assert route.view()["options"] == 2


def tutu_answering(stations: dict[str, list], timetable) -> TutuTrains:
    def handler(request: httpx.Request) -> httpx.Response:
        if "railway_simple" in str(request.url):
            return httpx.Response(200, json=stations.get(request.url.params["name"], []))
        return httpx.Response(200, json=timetable)

    return TutuTrains(httpx.AsyncClient(transport=httpx.MockTransport(handler)), gap_s=0)


STATIONS = {
    "Самарканд": [{"id": "2900700", "value": "Самарканд"}],
    "Ташкент": [{"id": "2900000", "value": "Ташкент"}],
}


def test_should_find_trains_between_two_cities_of_the_soviet_network():
    tutu = tutu_answering(
        STATIONS, {"trips": [AFROSIYOB], "url": "/poezda/rasp_d.php?nnst1=2900700&nnst2=2900000"}
    )

    found = asyncio.run(tutu.route(SAMARKAND, TASHKENT))

    assert found.best.name == "Афросиаб 768Ф"
    assert (found.best.departs, found.best.arrives) == ("18:49", "21:04")  # Moscow time → Uzbekistan, +2 h
    assert found.best.link == "https://www.tutu.ru/poezda/rasp_d.php?nnst1=2900700&nnst2=2900000"


def test_should_take_a_bare_empty_list_for_no_trains():
    tutu = tutu_answering(STATIONS, [])

    assert asyncio.run(tutu.route(SAMARKAND, TASHKENT)) is None


def test_should_not_ask_tutu_outside_its_railways():
    assert not TutuTrains(gap_s=0).covers(ISTANBUL)


def test_should_convert_bus_fares_from_euros_and_keep_the_day():
    rides = rides_from(
        [
            {
                "status": "available",
                "duration": {"hours": 11, "minutes": 30},
                "price": {"total": 32.99},
                "departure": {"date": "2026-11-15T00:45:00+03:00"},
                "arrival": {"date": "2026-11-15T12:15:00+03:00"},
                "legs": [{}],
            },
            {"status": "full", "duration": {"hours": 12}, "price": {"total": 20}},
        ],
        "https://shop.flixbus.com/search",
    )

    [ride] = rides
    assert ride.mode == "bus" and ride.dated and ride.minutes == 690
    assert 2_900 <= ride.price_rub <= 3_050  # 32.99 € at the bank rate of 24 October 2026


def test_should_match_a_bus_city_only_near_ours():
    def handler(request: httpx.Request) -> httpx.Response:
        if "autocomplete" in str(request.url):  # a namesake 900 km away is not our city
            return httpx.Response(
                200, json=[{"id": "far", "is_flixbus_city": True, "location": {"lat": 45, "lon": 40}}]
            )
        raise AssertionError("no search for a city we could not match")

    flix = FlixBuses(httpx.AsyncClient(transport=httpx.MockTransport(handler)))

    assert asyncio.run(flix.route(ISTANBUL, ANTALYA, date(2026, 11, 15))) is None


class Boom:
    def covers(self, place: City) -> bool:
        return True

    async def route(self, *_args):
        raise RuntimeError("timetable down")


def test_should_turn_a_failing_source_into_no_data():
    assert asyncio.run(GroundTransport(trains=Boom()).route(SAMARKAND, TASHKENT)) is None


def test_should_ask_buses_only_where_the_trains_do_not_run():
    asked = []

    class Buses:
        async def route(self, origin, destination, day=None):
            asked.append(origin.name)
            return GroundRoute(
                (GroundOption("bus", "flixbus", "FlixBus", None, None, 690, 2_977, None, "/x", True),)
            )

    ground = GroundTransport(trains=TutuTrains(gap_s=0), buses=Buses())

    found = asyncio.run(ground.route(ISTANBUL, ANTALYA))

    assert found.best.price_rub == 2_977 and asked == ["Стамбул"]
