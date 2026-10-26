"""Where people actually fly from a city: two Aviasales Data API calls, cached for half a day per city.

The route map is a public route list months behind (from Astana it still has Kyiv and misses Vienna). These
two answers are what Aviasales users found in the last days, with one change or none:
- city-directions: the popular directions from the city;
- v3/get_latest_prices over a year: every destination with a recent price.
Their union, as city codes, is the list search looks at; the route map only adds what they do not have.
A failure gives no live destinations, never an error: the route map still answers.
"""

import asyncio
import logging
import time
from typing import Protocol

import httpx

from app.flights import city_code

log = logging.getLogger(__name__)

DIRECTIONS_URL = "https://api.travelpayouts.com/v1/city-directions"
LATEST_URL = "https://api.travelpayouts.com/aviasales/v3/get_latest_prices"
TTL_S = 12 * 3600


class Directions(Protocol):
    async def destinations(self, origin: str) -> list[str]: ...


class NoDirections:
    """No TRAVELPAYOUTS_TOKEN: only the route map."""

    async def destinations(self, origin: str) -> list[str]:
        return []


class LiveDirections:
    def __init__(self, token: str, client: httpx.AsyncClient | None = None, ttl_s: float = TTL_S):
        self._token = token
        self._client = client or httpx.AsyncClient(timeout=10)
        self._ttl = ttl_s
        self._cache: dict[str, tuple[float, list[str]]] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def destinations(self, origin: str) -> list[str]:
        """City codes with recent tickets from the origin: popular ones first, then the rest by price."""
        home = city_code(origin)
        lock = self._locks.setdefault(home, asyncio.Lock())
        async with lock:  # two searches from one city share one pair of requests
            hit = self._cache.get(home)
            if hit and time.monotonic() - hit[0] < self._ttl:
                return hit[1]
            popular, latest = await asyncio.gather(self._popular(home), self._latest(home))
            found = [c for c in dict.fromkeys(popular + latest) if c and c != home]
            if found:  # an empty answer is a failure: asked again next time
                self._cache[home] = (time.monotonic(), found)
            return found

    async def _get(self, url: str, params: dict):
        try:
            response = await self._client.get(url, params={**params, "token": self._token})
            response.raise_for_status()
            return response.json().get("data")
        except (httpx.HTTPError, ValueError):
            log.warning("Aviasales directions failed: %s", url, exc_info=True)
            return None

    async def _popular(self, origin: str) -> list[str]:
        data = await self._get(DIRECTIONS_URL, {"origin": origin, "currency": "rub"}) or {}
        rows = data.values() if isinstance(data, dict) else data
        return [city_code(r.get("destination")) for r in rows if r.get("destination")]

    async def _latest(self, origin: str) -> list[str]:
        params = {
            "origin": origin,
            "period_type": "year",
            "one_way": "true",
            "limit": 1000,
            "currency": "rub",
        }
        rows = await self._get(LATEST_URL, params) or []
        cheapest: dict[str, int] = {}
        for r in rows:
            code = city_code(r.get("destination"))
            if code and r.get("value"):
                cheapest[code] = min(cheapest.get(code, r["value"]), r["value"])
        return sorted(cheapest, key=cheapest.get)
