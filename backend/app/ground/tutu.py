"""Trains from the Tutu.ru timetable, through Travelpayouts: no key, but a tight rate limit (an empty body when
asked too often), so requests go one at a time with a gap, an empty answer is retried once, and every answer
is kept for hours: a timetable changes twice a year.

The times come in Moscow time, as the «Экспресс» system keeps them for the whole network (Moscow →
Ekaterinburg departs and arrives by one clock), so they are turned into each station's local time.
"""

import asyncio
import logging
import re
import time
from datetime import date, datetime
from zoneinfo import ZoneInfo

import httpx

from app.flights.dictionary import City, time_zone
from app.ground.model import GroundOption, GroundRoute

log = logging.getLogger(__name__)

STATIONS_URL = "https://www.tutu.ru/suggest/railway_simple/"
TRAINS_URL = "https://suggest.travelpayouts.com/search"
SITE = "https://www.tutu.ru"
HEADERS = {"User-Agent": "Mozilla/5.0 (1surak travel agent prototype)"}
MIN_GAP_S = 3.0  # between two timetable requests: back to back they come back empty, 3 s apart never did
RETRY_AFTER_S = 4.0
CACHE_TTL_S = 12 * 3600
MOSCOW = ZoneInfo("Europe/Moscow")
# The railways Tutu sells and lists: the former Soviet network («Экспресс» station codes).
COUNTRIES = {
    "Россия",
    "Казахстан",
    "Узбекистан",
    "Кыргызстан",
    "Киргизия",
    "Беларусь",
    "Азербайджан",
    "Таджикистан",
}
FARES = {
    "sedentary": "сидячий",
    "plazcard": "плацкарт",
    "common": "общий",
    "coupe": "купе",
    "lux": "СВ",
    "soft": "люкс",
}


def _city_part(name: str) -> str:
    """«Дагестан (Махачкала)» → «Махачкала», «Санкт-Петербург» stays."""
    inside = re.search(r"\(([^)]+)\)", name)
    return (inside.group(1) if inside else name).strip()


def _minutes(seconds: str | int | None) -> int | None:
    try:
        return round(int(seconds) / 60)
    except (TypeError, ValueError):
        return None


def _local(clock: str | None, zone: ZoneInfo | None) -> str | None:
    """«04:33» Moscow time → «06:33» in Tashkent; unchanged without a known time zone."""
    if not clock or len(clock) < 5:
        return None
    if not zone:
        return clock[:5]
    moscow = datetime.combine(date.today(), datetime.strptime(clock[:5], "%H:%M").time(), MOSCOW)
    return moscow.astimezone(zone).strftime("%H:%M")


def trains_from(
    trips: list[dict], link: str, leaves: ZoneInfo | None = None, arrives: ZoneInfo | None = None
) -> list[GroundOption]:
    """Every train with its cheapest fare, the times by the clock of the station it leaves or reaches."""
    found = []
    for trip in trips:
        minutes = _minutes(trip.get("travelTimeInSeconds"))
        if not minutes:
            continue
        fares = [c for c in trip.get("categories") or [] if c.get("price")]
        cheapest = min(fares, key=lambda c: c["price"]) if fares else None
        number = trip.get("trainNumber") or ""
        title = (trip.get("name") or "").strip()
        found.append(
            GroundOption(
                mode="train",
                source="tutu",
                name=f"{title} {number}".strip() if title else f"Поезд {number}".strip(),
                departs=_local(trip.get("departureTime"), leaves),
                arrives=_local(trip.get("arrivalTime"), arrives),
                minutes=minutes,
                price_rub=int(cheapest["price"]) if cheapest else None,
                fare=FARES.get(cheapest["type"], cheapest["type"]) if cheapest else None,
                link=link,
            )
        )
    return found


class TutuTrains:
    def __init__(
        self, client: httpx.AsyncClient | None = None, timeout_s: float = 8.0, gap_s: float = MIN_GAP_S
    ):
        self._client = client or httpx.AsyncClient(timeout=timeout_s, headers=HEADERS)
        self._gap = gap_s
        self._turn = asyncio.Lock()
        self._last = 0.0
        self._stations: dict[str, str | None] = {}
        self._routes: dict[tuple[str, str], tuple[float, GroundRoute | None]] = {}

    def covers(self, place: City) -> bool:
        return place.country in COUNTRIES

    async def _paced_get(self, url: str, params: dict) -> httpx.Response:
        async with self._turn:  # one request at a time, at least `gap` apart
            wait = self._last + self._gap - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            try:
                return await self._client.get(url, params=params)
            finally:
                self._last = time.monotonic()

    async def station(self, place: City) -> str | None:
        name = _city_part(place.name)
        if name in self._stations:
            return self._stations[name]
        try:
            response = await self._client.get(STATIONS_URL, params={"name": name})
            rows = response.json() if response.content else []
        except (httpx.HTTPError, ValueError):
            log.warning("Tutu station lookup failed for %s", name, exc_info=True)
            return None  # not cached: try again next time
        exact = next((r["id"] for r in rows if r.get("value") == name), None)
        prefixed = next((r["id"] for r in rows if str(r.get("value", "")).startswith(name)), None)
        self._stations[name] = exact or prefixed
        return self._stations[name]

    async def route(self, origin: City, destination: City) -> GroundRoute | None:
        if not (self.covers(origin) and self.covers(destination)):
            return None
        a, b = await self.station(origin), await self.station(destination)
        if not a or not b or a == b:
            return None
        cached = self._routes.get((a, b))
        if cached and time.monotonic() - cached[0] < CACHE_TTL_S:
            return cached[1]
        params = {"service": "tutu_trains", "term": a, "term2": b}
        try:
            response = await self._paced_get(TRAINS_URL, params)
            if not response.content:  # rate limited: the body comes back empty
                await asyncio.sleep(RETRY_AFTER_S)
                response = await self._paced_get(TRAINS_URL, params)
            if not response.content:
                return None
            data = response.json()
        except (httpx.HTTPError, ValueError):
            log.warning("Tutu timetable failed for %s>%s", a, b, exc_info=True)
            return None
        if not isinstance(data, dict):  # no trains between the two: the answer is a bare []
            self._routes[(a, b)] = (time.monotonic(), None)
            return None
        link = SITE + data["url"] if data.get("url") else f"{SITE}/poezda/rasp_d.php?nnst1={a}&nnst2={b}"
        options = trains_from(data.get("trips") or [], link, time_zone(origin), time_zone(destination))
        result = GroundRoute(tuple(options)) if options else None
        self._routes[(a, b)] = (time.monotonic(), result)
        return result
