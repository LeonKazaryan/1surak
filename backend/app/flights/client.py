"""Flight prices from Aviasales (Travelpayouts Data API): the cheapest tickets people found in the last days.

Not a live search: prices are cached by Aviasales, so the agent says «по данным Aviasales на дату».
Every failure becomes «no data» for that route, never an exception: the agent then says it honestly.
"""

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Protocol

import httpx

from app.flights.dictionary import airline_name, city_code, logo_url

if TYPE_CHECKING:
    from app.flights.fares import FareStore

log = logging.getLogger(__name__)

PRICES_URL = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"
AVIASALES = "https://www.aviasales.ru"
CACHE_TTL_S = 6 * 3600
MAX_PARALLEL = 8
TICKETS_PER_ROUTE = 30

FareKey = tuple[str, str, str]  # origin city, destination city, "YYYY-MM" or "" for the nearest dates


@dataclass(frozen=True)
class Ticket:
    origin_airport: str
    destination_airport: str
    airline: str
    flight_number: str
    departure_at: str  # ISO with the local offset
    price: int  # RUB, one way, one passenger
    transfers: int
    duration_min: int
    link: str

    def view(self) -> dict:
        return {
            "price_rub": self.price,
            "airline": self.airline,
            "airline_name": airline_name(self.airline),
            "logo": logo_url(self.airline),
            "flight_number": f"{self.airline} {self.flight_number}",
            "transfers": self.transfers,
            "hours": round(self.duration_min / 60 * 2) / 2,
            "departure": self.departure_at[:16].replace("T", " "),
            "from_airport": self.origin_airport,
            "to_airport": self.destination_airport,
            "link": f"{AVIASALES}{self.link}",
        }


@dataclass(frozen=True)
class RouteFlights:
    cheapest: Ticket
    direct: Ticket | None  # the cheapest without transfers, if any
    fastest: Ticket

    @property
    def duration_min(self) -> int:
        return (self.direct or self.fastest).duration_min

    def view(self) -> dict:
        view = {**self.cheapest.view(), "direct_available": self.direct is not None}
        if self.direct and self.direct is not self.cheapest:
            view["direct_option"] = self.direct.view()
        return view


class Flights(Protocol):
    async def route(self, origin: str, destination: str, month: int | None = None) -> RouteFlights | None: ...

    async def routes(
        self, origin: str, destinations: list[str], month: int | None
    ) -> dict[str, RouteFlights | None]: ...


class NoFlights:
    """No TRAVELPAYOUTS_TOKEN: every route has no data, and the agent says so."""

    async def route(self, origin: str, destination: str, month: int | None = None) -> RouteFlights | None:
        return None

    async def routes(
        self, origin: str, destinations: list[str], month: int | None
    ) -> dict[str, RouteFlights | None]:
        return dict.fromkeys(destinations)


def departure_month(month: int | None, today: date | None = None) -> str | None:
    """«ноябрь» means the coming November: this year if it has not passed, otherwise the next."""
    if month is None:
        return None
    today = today or date.today()
    year = today.year if month >= today.month else today.year + 1
    return f"{year}-{month:02d}"


def summarize(rows: list[dict]) -> RouteFlights | None:
    tickets = [
        Ticket(
            origin_airport=r.get("origin_airport") or r.get("origin", ""),
            destination_airport=r.get("destination_airport") or r.get("destination", ""),
            airline=r.get("airline", ""),
            flight_number=str(r.get("flight_number", "")),
            departure_at=r.get("departure_at", ""),
            price=int(r["price"]),
            transfers=int(r.get("transfers") or 0),
            duration_min=int(r.get("duration_to") or r.get("duration") or 0),
            link=r.get("link", ""),
        )
        for r in rows
        if r.get("price")
    ]
    if not tickets:
        return None
    direct = [t for t in tickets if t.transfers == 0]
    timed = [t for t in tickets if t.duration_min] or tickets
    return RouteFlights(
        cheapest=min(tickets, key=lambda t: t.price),
        direct=min(direct, key=lambda t: t.price) if direct else None,
        fastest=min(timed, key=lambda t: (t.duration_min or 10**6, t.price)),
    )


class TravelpayoutsFlights:
    """Looks in memory, then in the fares table, then asks Aviasales, only for what is still missing."""

    def __init__(
        self,
        token: str,
        client: httpx.AsyncClient | None = None,
        timeout_s: float = 8.0,
        store: "FareStore | None" = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self._token = token
        self._client = client or httpx.AsyncClient(timeout=timeout_s)
        self._store = store
        self._clock = clock
        self._cache: dict[FareKey, tuple[datetime, RouteFlights | None]] = {}
        self._parallel = asyncio.Semaphore(MAX_PARALLEL)

    async def route(self, origin: str, destination: str, month: int | None = None) -> RouteFlights | None:
        return (await self.routes(origin, [destination], month))[destination]

    async def routes(
        self, origin: str, destinations: list[str], month: int | None
    ) -> dict[str, RouteFlights | None]:
        when = departure_month(month) or ""
        keys = {d: (city_code(origin), city_code(d), when) for d in destinations}
        wanted = {k for k in keys.values() if k[0] and k[1] and k[0] != k[1]}
        found = await self._lookup(wanted)
        return {d: found.get(key) for d, key in keys.items()}

    async def _lookup(self, keys: set[FareKey]) -> dict[FareKey, RouteFlights | None]:
        now = self._clock()
        found = {k: hit[1] for k in keys if (hit := self._cache.get(k)) and hit[0] > now}
        missing = keys - found.keys()
        if missing and self._store:
            stored = await self._store.load(sorted(missing), now)
            self._cache.update(stored)
            found.update({k: result for k, (_, result) in stored.items()})
            missing -= stored.keys()
        if not missing:
            return found
        order = sorted(missing)
        answers = await asyncio.gather(*(self._fetch(*k) for k in order))
        fresh = {k: a for k, a in zip(order, answers, strict=True) if a is not _FAILED}
        expires = now + timedelta(seconds=CACHE_TTL_S)
        self._cache.update({k: (expires, a) for k, a in fresh.items()})
        if fresh and self._store:
            await self._store.save(fresh, now, expires)
        return {**found, **dict.fromkeys(missing), **fresh}

    async def _fetch(self, origin: str, destination: str, month: str):
        params = {
            "origin": origin,
            "destination": destination,
            "one_way": "true",
            "currency": "rub",
            "sorting": "price",
            "limit": TICKETS_PER_ROUTE,
            "token": self._token,
        }
        if month:
            params["departure_at"] = month
        try:
            async with self._parallel:
                response = await self._client.get(PRICES_URL, params=params)
            response.raise_for_status()
            return summarize(response.json().get("data") or [])
        except (httpx.HTTPError, ValueError, KeyError):
            log.warning("Travelpayouts failed for %s>%s", origin, destination, exc_info=True)
            return _FAILED  # not cached: the next search tries again


_FAILED = object()
