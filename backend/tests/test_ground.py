"""Trains and buses: what the timetables answer, how it is read, and that a failing source never breaks a route."""

import asyncio
from datetime import date

import httpx

from app.flights.dictionary import City
from app.ground import GroundOption, GroundRoute, GroundTransport
from app.ground.flixbus import FlixBuses, rides_from
from app.ground.service import merged
from app.ground.tutu import TutuTrains, trains_from
from app.ground.yandex import YandexRasp
from app.ground.yandex import rides_from as rides_from_yandex

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


LASTOCHKA = {
    "thread": {
        "number": "7922",
        "transport_type": "suburban",
        "transport_subtype": {"title": "Ласточка «Экспресс»  - состав 5 вагонов"},
    },
    "departure": "2026-11-15T07:40:00+03:00",
    "arrival": "2026-11-15T09:28:00+03:00",
    "duration": 6480.0,
    "tickets_info": {"places": [{"price": {"whole": 900, "cents": 0}, "currency": "RUB"}]},
}
NIGHT_123 = {
    "thread": {"number": "123Ф", "transport_type": "train", "transport_subtype": {"title": None}},
    "departure": "2026-11-15T00:33:00+05:00",
    "arrival": "2026-11-15T04:48:00+05:00",
    "duration": 15300.0,
    "tickets_info": {"places": []},
}
PLANE = {
    "thread": {"number": "KC 109", "transport_type": "plane"},
    "departure": "2026-11-15T17:10:00+05:00",
    "duration": 6900.0,
}


def test_should_read_yandex_rides_and_leave_the_planes_out():
    rides = rides_from_yandex([LASTOCHKA, NIGHT_123, PLANE], "https://rasp.yandex.ru/search/", dated=True)

    assert [(r.name, r.mode, r.minutes, r.price_rub, r.number) for r in rides] == [
        ("Ласточка «Экспресс» 7922", "train", 108, 900, "7922"),
        ("Поезд 123Ф", "train", 255, None, "123Ф"),
    ]
    assert rides[0].view()["credit"]["text"] == "Данные предоставлены сервисом Яндекс.Расписания"
    typical = rides_from_yandex([NIGHT_123], "/", dated=False)
    assert (typical[0].departs, typical[0].arrives, typical[0].dated) == ("00:33", "04:48", False)


def yandex_answering(segments: list[dict], asked: list) -> YandexRasp:
    def handler(request: httpx.Request) -> httpx.Response:
        if "nearest_settlement" in str(request.url):
            code = "c10334" if float(request.url.params["lat"]) < 40 else "c10335"
            return httpx.Response(200, json={"type": "settlement", "code": code})
        asked.append(request.url.params["date"])
        return httpx.Response(200, json={"segments": segments})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return YandexRasp("key", client, today=lambda: date(2026, 10, 26))


def test_should_ask_yandex_for_the_day_or_a_typical_one_past_its_timetables():
    asked = []
    rasp = yandex_answering([NIGHT_123], asked)

    near = asyncio.run(rasp.route(SAMARKAND, TASHKENT, date(2026, 11, 15)))
    far = asyncio.run(rasp.route(SAMARKAND, TASHKENT, date(2027, 5, 20)))

    assert asked == ["2026-11-15", "2026-11-09"]  # May 2027 is not out yet: two weeks from today instead
    assert near.best.dated and not far.best.dated
    assert near.best.link == "https://rasp.yandex.ru/search/?fromId=c10334&toId=c10335&when=2026-11-15"


def test_should_join_one_train_from_both_sources_and_add_the_rest():
    # Tutu lists it as 124*Ф, Yandex as 123Ф: a train's number turns even where it changes direction
    tutu = GroundOption(
        "train", "tutu", "Поезд 123Ф", "00:33", "04:48", 240, 1_387, "плацкарт", "/tutu", number="124*Ф"
    )
    [night, lastochka] = rides_from_yandex([NIGHT_123, LASTOCHKA], "/yandex", dated=True)

    joined = merged((tutu,), (night, lastochka))

    assert len(joined) == 2
    assert (joined[0].departs, joined[0].price_rub, joined[0].link) == (
        "2026-11-15T00:33:00+05:00",
        1_387,
        "/tutu",
    )
    assert joined[0].source == "yandex"  # its times are Yandex's, so the card credits Yandex
    assert joined[1].name == "Ласточка «Экспресс» 7922"


def test_should_tidy_yandex_names_and_prefer_rides_with_a_fare():
    express = {
        **LASTOCHKA,
        "thread": {
            "number": "7001/7002/7004",
            "transport_type": "suburban",
            "transport_subtype": {"title": "экспресс (билеты c указанием мест)"},
        },
        "tickets_info": {"places": []},
    }
    rides = rides_from_yandex([express, NIGHT_123, LASTOCHKA], "/", dated=True)

    assert rides[0].name == "Экспресс 7001" and rides[0].number == "7001"
    assert GroundRoute(tuple(rides)).best.name == "Ласточка «Экспресс» 7922"  # the only one with a known fare
