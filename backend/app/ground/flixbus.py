"""Buses from FlixBus: the JSON its own website searches with (undocumented, no key), so it can change or block
without notice. Rides are for a given day, priced in euros, converted to roubles at the bank rate in app.money.
"""

import logging
import time
from datetime import date, datetime, timedelta

import httpx

from app.flights.dictionary import City, distance_km
from app.ground.model import GroundOption, GroundRoute
from app.money import CURRENCIES

log = logging.getLogger(__name__)

API = "https://global.api.flixbus.com"
SHOP = "https://shop.flixbus.com/search"
HEADERS = {"User-Agent": "Mozilla/5.0 (1surak travel agent prototype)"}
SAME_CITY_KM = 60  # an autocomplete hit further than this from our city is another town with that name
CACHE_TTL_S = 3 * 3600
LEAD_DAYS = 14  # without a day, look two weeks ahead: a typical day, not a sold-out tomorrow


def _minutes(duration: dict | None) -> int | None:
    if not duration:
        return None
    return int(duration.get("hours", 0)) * 60 + int(duration.get("minutes", 0)) or None


def rides_from(results: list[dict], link: str) -> list[GroundOption]:
    euro = CURRENCIES["EUR"]
    found = []
    for ride in results:
        minutes = _minutes(ride.get("duration"))
        if not minutes or ride.get("status") not in (None, "available"):
            continue
        total = (ride.get("price") or {}).get("total")
        found.append(
            GroundOption(
                mode="bus",
                source="flixbus",
                name="FlixBus"
                + (f", {len(ride['legs'])} автобуса" if len(ride.get("legs") or []) > 1 else ""),
                departs=(ride.get("departure") or {}).get("date"),
                arrives=(ride.get("arrival") or {}).get("date"),
                minutes=minutes,
                price_rub=euro.to_rub(total) if total else None,
                fare=None,
                link=link,
                dated=True,
            )
        )
    return found


class FlixBuses:
    def __init__(self, client: httpx.AsyncClient | None = None, timeout_s: float = 8.0):
        self._client = client or httpx.AsyncClient(timeout=timeout_s, headers=HEADERS)
        self._cities: dict[str, str | None] = {}
        self._rides: dict[tuple[str, str, str], tuple[float, GroundRoute | None]] = {}

    async def city_id(self, place: City) -> str | None:
        if place.code in self._cities:
            return self._cities[place.code]
        try:
            response = await self._client.get(
                f"{API}/search/autocomplete/cities",
                params={"q": place.name, "lang": "ru", "flixbus_cities_only": "false"},
            )
            rows = response.json()
        except (httpx.HTTPError, ValueError):
            log.warning("FlixBus city lookup failed for %s", place.name, exc_info=True)
            return None
        near = [
            r
            for r in rows
            if r.get("is_flixbus_city")
            and distance_km(place, _point(r.get("location") or {})) <= SAME_CITY_KM
        ]
        self._cities[place.code] = near[0]["id"] if near else None
        return self._cities[place.code]

    async def route(self, origin: City, destination: City, day: date | None = None) -> GroundRoute | None:
        a, b = await self.city_id(origin), await self.city_id(destination)
        if not a or not b or a == b:
            return None
        day = day or date.today() + timedelta(days=LEAD_DAYS)
        key = (a, b, day.isoformat())
        cached = self._rides.get(key)
        if cached and time.monotonic() - cached[0] < CACHE_TTL_S:
            return cached[1]
        when = day.strftime("%d.%m.%Y")
        try:
            response = await self._client.get(
                f"{API}/search/service/v4/search",
                params={
                    "from_city_id": a,
                    "to_city_id": b,
                    "departure_date": when,
                    "products": '{"adult":1}',
                    "currency": "EUR",
                    "locale": "ru",
                    "search_by": "cities",
                    "include_after_midnight_rides": "1",
                },
            )
            data = response.json()
        except (httpx.HTTPError, ValueError):
            log.warning("FlixBus search failed for %s>%s", origin.name, destination.name, exc_info=True)
            return None
        link = f"{SHOP}?departureCity={a}&arrivalCity={b}&rideDate={when}&adult=1"
        results = [r for trip in data.get("trips") or [] for r in (trip.get("results") or {}).values()]
        options = rides_from(results, link)
        found = GroundRoute(tuple(options)) if options else None
        self._rides[key] = (time.monotonic(), found)
        return found


def _point(location: dict) -> City:
    return City("", "", "", float(location.get("lat", 0)), float(location.get("lon", 0)))


def parse_moment(value: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(value) if value else None
    except ValueError:
        return None
