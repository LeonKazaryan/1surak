"""Real tickets from Travelpayouts: parsing, caching, failures, and the departure city of each request."""

import asyncio
from datetime import date

import httpx

from app.flights import city, nearest
from app.flights.client import TravelpayoutsFlights, departure_month, summarize

ROWS = [
    {
        "price": 9000,
        "airline": "PC",
        "flight_number": 1,
        "transfers": 1,
        "duration_to": 600,
        "link": "/a",
        "origin_airport": "NQZ",
        "destination_airport": "SAW",
        "departure_at": "2026-11-12T05:00:00+06:00",
    },
    {
        "price": 10558,
        "airline": "PC",
        "flight_number": 229,
        "transfers": 0,
        "duration_to": 345,
        "link": "/b",
        "origin_airport": "NQZ",
        "destination_airport": "SAW",
        "departure_at": "2026-11-13T05:05:00+06:00",
    },
]


def test_should_keep_the_cheapest_and_the_cheapest_direct_ticket():
    found = summarize(ROWS)

    assert found.cheapest.price == 9000 and found.direct.price == 10558
    assert found.duration_min == 345  # the direct one sets the flight time
    view = found.view()
    assert view["transfers"] == 1 and view["direct_available"] is True
    assert view["direct_option"]["price_rub"] == 10558
    assert view["link"] == "https://www.aviasales.ru/a" and view["airline_name"] == "Pegasus Airlines"


def test_should_read_a_month_as_the_coming_one():
    assert departure_month(11, date(2026, 10, 25)) == "2026-11"
    assert departure_month(3, date(2026, 10, 25)) == "2027-03"
    assert departure_month(None) is None


def client_answering(handler) -> TravelpayoutsFlights:
    return TravelpayoutsFlights("token", httpx.AsyncClient(transport=httpx.MockTransport(handler)))


def test_should_ask_aviasales_once_per_route_and_month():
    asked = []

    def handler(request: httpx.Request) -> httpx.Response:
        asked.append(dict(request.url.params))
        return httpx.Response(200, json={"data": ROWS})

    flights = client_answering(handler)

    async def twice():
        await flights.route("NQZ", "IST", 11)
        return await flights.route("NQZ", "IST", 11)

    assert asyncio.run(twice()).cheapest.price == 9000
    assert len(asked) == 1
    assert asked[0]["origin"] == "NQZ" and asked[0]["destination"] == "IST" and asked[0]["one_way"] == "true"


def test_should_turn_an_api_failure_into_no_data():
    flights = client_answering(lambda request: httpx.Response(500))

    assert asyncio.run(flights.route("NQZ", "IST", 11)) is None


def test_should_suggest_the_nearest_cities_with_an_airport():
    codes = [c.code for c in nearest(51.15, 71.42, 3)]

    assert codes[0] == "NQZ"
    assert city("nqz").from_text == "из Астаны"


def test_should_list_nearby_departure_cities(client):
    items = client.get("/api/places/nearby", params={"lat": 55.75, "lon": 37.62, "limit": 3}).json()["items"]

    assert items[0]["code"] == "MOW" and items[0]["name"] == "Москва"
    assert client.get("/api/places/nearby", params={"lat": 200, "lon": 0}).status_code == 422
