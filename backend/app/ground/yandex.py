"""Trains, suburban trains and buses from the Yandex.Rasp API (a free key: YANDEX_RASP_KEY).

It answers for one day, in local times: with fares for much of Russia (trains, «Ласточки», suburban trains,
intercity buses), without fares in Kazakhstan, Uzbekistan and Belarus; Georgia and Azerbaijan come back empty.
Timetables are published a month or so ahead, so a trip further off is looked up on a day two weeks from now:
a typical timetable, not that day's.

The terms (yandex.ru/legal/timetable_api) allow caching only for a while, and every screen that shows the data
must say «Данные предоставлены сервисом Яндекс.Расписания» with a link to rasp.yandex.ru: an option from here
carries that line in its view for the cards.
"""

import asyncio
import logging
import re
import time
from collections.abc import Callable
from datetime import date, timedelta

import httpx

from app.flights.dictionary import City
from app.ground.model import GroundOption, GroundRoute
from app.ground.tutu import COUNTRIES
from app.money import CURRENCIES

log = logging.getLogger(__name__)

API = "https://api.rasp.yandex.net/v3.0"
SITE = "https://rasp.yandex.ru"
NEAR_KM = 30  # the Yandex settlement nearest to our city's centre, no further than this
HORIZON_DAYS = 30  # timetables further ahead are not out yet: the answer would be empty
LEAD_DAYS = 14  # without a day (or past the horizon), a typical day two weeks ahead
CACHE_TTL_S = 6 * 3600
MODES = {"train": "train", "suburban": "train", "bus": "bus"}  # planes and boats are not hops by land
GENERIC = {"train": "Поезд", "suburban": "Электричка", "bus": "Автобус"}


def _fare(tickets: dict | None) -> int | None:
    """The cheapest seat in roubles, from the prices Yandex knows (often none outside Russia)."""
    found = []
    for place in (tickets or {}).get("places") or []:
        price = place.get("price") or {}
        if price.get("whole") is None:
            continue
        amount = price["whole"] + (price.get("cents") or 0) / 100
        currency = place.get("currency") or "RUB"
        if currency == "RUB":
            found.append(round(amount))
        elif currency in CURRENCIES:
            found.append(CURRENCIES[currency].to_rub(amount))
    return min(found) if found else None


def _number(thread: dict) -> str | None:
    """«7001/7002/7004» → «7001»: a suburban train renumbered on the way is still one train."""
    return (thread.get("number") or "").split("/")[0].strip() or None


def _name(thread: dict) -> str:
    """«Ласточка «Экспресс» 7922», «Поезд 030У», «Автобус»: the train's kind when Yandex names it, without
    the notes in brackets or after a dash («экспресс (билеты c указанием мест)» → «Экспресс»)."""
    kind = thread.get("transport_type") or "train"
    subtype = (thread.get("transport_subtype") or {}).get("title") or ""
    subtype = re.split(r"\s+-\s+|\s*\(", subtype)[0].strip()
    title = subtype[:1].upper() + subtype[1:] if subtype else GENERIC.get(kind, "Поезд")
    return f"{title} {_number(thread) or ''}".strip()


def rides_from(segments: list[dict], link: str, dated: bool) -> list[GroundOption]:
    """Direct trains and buses of one day. A ride on the trip's own day keeps its date and time with the
    offset; one from a typical day keeps only the clock."""
    found = []
    for segment in segments:
        thread = segment.get("thread") or {}
        mode = MODES.get(thread.get("transport_type"))
        minutes = round(float(segment.get("duration") or 0) / 60)
        departs, arrives = segment.get("departure"), segment.get("arrival")
        if not mode or segment.get("has_transfers") or not minutes or not departs:
            continue
        found.append(
            GroundOption(
                mode=mode,
                source="yandex",
                name=_name(thread),
                departs=departs if dated else departs[11:16],
                arrives=(arrives if dated else arrives[11:16]) if arrives else None,
                minutes=minutes,
                price_rub=_fare(segment.get("tickets_info")),
                fare=None,
                link=link,
                dated=dated,
                number=_number(thread),
            )
        )
    return found


class YandexRasp:
    def __init__(
        self,
        key: str,
        client: httpx.AsyncClient | None = None,
        timeout_s: float = 8.0,
        today: Callable[[], date] = date.today,
    ):
        self._key = key
        self._client = client or httpx.AsyncClient(timeout=timeout_s)
        self._today = today
        self._settlements: dict[tuple[float, float], str | None] = {}
        self._routes: dict[tuple[str, str, date], tuple[float, GroundRoute | None]] = {}

    def covers(self, place: City) -> bool:
        return place.country in COUNTRIES

    async def _get(self, path: str, **params) -> dict | None:
        try:
            response = await self._client.get(
                f"{API}/{path}/", params={"apikey": self._key, "format": "json", "lang": "ru_RU", **params}
            )
            if response.status_code != 200:  # the URL carries the key: never log it
                log.warning("Yandex.Rasp %s answered %s", path, response.status_code)
                return None
            return response.json()
        except (httpx.HTTPError, ValueError) as problem:
            log.warning("Yandex.Rasp %s failed: %s", path, type(problem).__name__)
            return None

    async def settlement(self, place: City) -> str | None:
        """Yandex's code of the town at our city's coordinates: «c10335» for Tashkent."""
        spot = (round(place.lat, 3), round(place.lon, 3))
        if spot in self._settlements:
            return self._settlements[spot]
        data = await self._get("nearest_settlement", lat=place.lat, lng=place.lon, distance=NEAR_KM)
        if data is None:
            return None  # not cached: try again next time
        code = data.get("code") if data.get("type") == "settlement" else None
        self._settlements[spot] = code
        return code

    async def route(self, origin: City, destination: City, day: date | None = None) -> GroundRoute | None:
        if not (self.covers(origin) and self.covers(destination)):
            return None
        a, b = await asyncio.gather(self.settlement(origin), self.settlement(destination))
        if not a or not b or a == b:
            return None
        today = self._today()
        dated = day is not None and today <= day <= today + timedelta(days=HORIZON_DAYS)
        when = day if dated else today + timedelta(days=LEAD_DAYS)
        cached = self._routes.get((a, b, when))
        if cached and time.monotonic() - cached[0] < CACHE_TTL_S:
            return cached[1]
        params = {"from": a, "to": b, "date": when.isoformat(), "transfers": "false", "limit": 200}
        data = await self._get("search", **params)
        if data is None:
            return None
        link = f"{SITE}/search/?fromId={a}&toId={b}&when={when.isoformat()}"
        options = rides_from(data.get("segments") or [], link, dated)
        result = GroundRoute(tuple(options)) if options else None
        self._routes[(a, b, when)] = (time.monotonic(), result)
        return result
