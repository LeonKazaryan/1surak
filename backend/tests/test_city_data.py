"""The sea only where it matters, taxi fares from the web, the day's exchange rates."""

import asyncio
import json
from datetime import UTC, date, datetime
from types import SimpleNamespace

import httpx

from app.catalog.catalog import load_catalog
from app.catalog.search import build_snapshot, card, describe
from app.fx import Rates
from app.kb.web import WebResult
from app.plan.hotels import Party, hotels_for
from app.plan.places import place_info
from app.plan.taxi import TaxiFares, checked_fare, estimated_ride_rub, price_level, ride_price
from app.plan.transfers import transfer_to

NOW = datetime(2026, 10, 27, 12, tzinfo=UTC)
CATALOG = load_catalog()


def test_should_keep_the_sea_out_of_a_city_trip_to_new_york():
    nyc = CATALOG.find("city-nyc")
    snapshot = build_snapshot(nyc, {}, {}, {})
    snapshot.climate[5] = {"air_max": 21.0, "sea_temp": 15.0}

    assert nyc.kinds[0] == "city"
    assert (
        "sea_temp" not in (card(snapshot, 5)["climate"] or {}) and "sea" not in card(snapshot, 5)["climate"]
    )
    assert "море" not in describe(snapshot, 5)["climate"]
    assert card(snapshot, 5, sea=True)["climate"]["sea"] == 15  # asked for the sea: then it is there


def test_should_keep_the_sea_of_a_beach_place():
    antalya = CATALOG.find("antalya")
    snapshot = build_snapshot(antalya, {}, {}, {})
    snapshot.climate[6] = {"air_max": 31.0, "sea_temp": 25.0}

    assert antalya.kinds[0] == "sea" and card(snapshot, 6)["climate"]["sea"] == 25


NYC_TLC = WebResult(
    url="https://www.nyc.gov/site/tlc/passengers/taxi-fare.page",
    title="Taxi Fare - TLC",
    content="Trips between JFK Airport and Manhattan: a flat fare of $70 plus surcharges, tolls and tip.",
)


def test_should_take_a_taxi_fare_only_with_its_quote():
    answer = {
        "found": True,
        "low": 70,
        "high": 70,
        "currency": "usd",
        "covers": "такси из JFK на Манхэттен",
        "source": 1,
        "quote": "a flat fare of $70",
    }

    fare = checked_fare(answer, [NYC_TLC], NOW.date())

    assert (fare.amount, fare.currency, fare.source) == (70, "USD", "nyc.gov")
    assert checked_fare({**answer, "quote": "a flat fare of $52"}, [NYC_TLC], NOW.date()) is None
    assert checked_fare({**answer, "low": 7, "high": 70}, [NYC_TLC], NOW.date()) is None  # a range too wide
    assert checked_fare({**answer, "low": 0.5, "high": 0.5, "quote": "$70"}, [NYC_TLC], NOW.date()) is None


def test_should_scale_the_city_fare_to_the_hotel_and_price_the_rest_by_the_country():
    fare = checked_fare(
        {"found": True, "low": 70, "high": 70, "currency": "USD", "covers": "", "source": 1, "quote": "$70"},
        [NYC_TLC],
        NOW.date(),
    )

    centre = ride_price(fare, 5_600, km=25, km_to_centre=25, country_code="US")
    near = ride_price(fare, 5_600, km=5, km_to_centre=25, country_code="US")
    assert centre.rub == 5_600 and centre.source == "nyc.gov" and 2_000 < near.rub < 5_600

    assert price_level("US") == 1.0 and price_level("KZ") < 0.4
    assert estimated_ride_rub(25, "US") > 2.5 * estimated_ride_rub(25, "KZ")  # no single rate for the world
    assert ride_price(None, None, 25, 25, "US").source is None


def test_should_price_a_transfer_by_the_city_fare_when_there_is_one():
    antalya = CATALOG.find("antalya")
    hotel = hotels_for(antalya, 11)[0]
    fare = checked_fare(
        {
            "found": True,
            "low": 15,
            "high": 20,
            "currency": "EUR",
            "covers": "",
            "source": 1,
            "quote": "€15 - €20",
        },
        [
            WebResult(
                url="https://www.antalya-airport.aero/taxi",
                title="Taxi",
                content="Taxi €15 - €20 to the centre",
            )
        ],
        NOW.date(),
    )

    ride = transfer_to(hotel, antalya, place_info("antalya"), Party(adults=6), fare, 1_600)

    assert ride.source == "antalya-airport.aero" and ride.price_rub % 100 == 0
    assert ride.price_rub >= 2 * 500  # six guests fill two cars


def model_answering(answer: dict):
    async def create(**kwargs):
        message = SimpleNamespace(content=json.dumps(answer))
        return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=None)

    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))


class Search:
    def __init__(self, results):
        self.results, self.asked = results, []

    async def search(self, query):
        self.asked.append(query)
        return self.results


def test_should_look_a_city_fare_up_once():
    search = Search([NYC_TLC])
    client = model_answering(
        {
            "found": True,
            "low": 70,
            "high": 70,
            "currency": "USD",
            "covers": "JFK",
            "source": 1,
            "quote": "$70",
        }
    )
    taxi = TaxiFares(None, [search], client, "m", CATALOG.find, now=lambda: NOW)

    async def run():
        first = await taxi.fares(["city-nyc", "city-nyc"], wait_s=None)
        return first, await taxi.fares(["city-nyc"], wait_s=None)

    first, again = asyncio.run(run())

    assert first["city-nyc"].amount == 70 and again["city-nyc"].source == "nyc.gov"
    assert len(search.asked) == 1 and "NYC airport taxi fare" in search.asked[0]


def test_should_convert_any_currency_by_the_days_rates():
    def handler(request: httpx.Request) -> httpx.Response:
        valutes = {
            "THB": {"Nominal": 10, "Value": 23.8195},
            "USD": {"Nominal": 1, "Value": 80.4909},
        }
        return httpx.Response(200, json={"Date": "2026-10-27", "Valute": valutes})

    rates = Rates(httpx.AsyncClient(transport=httpx.MockTransport(handler)))

    assert asyncio.run(rates.to_rub(500, "THB")) == round(500 * 2.38195)
    assert rates.rub(70, "usd") == round(70 * 80.4909)
    assert rates.rub(10, "XYZ") is None
    assert Rates().rub(1000, "KZT") == round(1000 / 5.561828)  # before any fetch: the app's fixed rates


def test_should_not_date_a_found_fare_wrong():
    fare = checked_fare(
        {"found": True, "low": 70, "high": 70, "currency": "USD", "covers": "", "source": 1, "quote": "$70"},
        [NYC_TLC],
        date(2026, 10, 27),
    )

    assert fare.checked == "2026-10-27"
