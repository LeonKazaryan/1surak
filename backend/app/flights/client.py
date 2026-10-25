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
from app.flights.freshness import STALE_FOR, Popularity, RateLimit, fare_ttl

if TYPE_CHECKING:
    from app.flights.fares import FareStore
    from app.flights.network import Network

log = logging.getLogger(__name__)

PRICES_URL = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"
AVIASALES = "https://www.aviasales.ru"
MAX_PARALLEL = 8
TICKETS_PER_ROUTE = 100  # more tickets, more days in the calendar (by_day)

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

    @property
    def departs(self) -> datetime | None:
        try:
            return datetime.fromisoformat(self.departure_at)
        except ValueError:
            return None

    @property
    def arrives(self) -> datetime | None:
        """Departure plus duration: aware datetimes, so time zones need no care."""
        start = self.departs
        return start + timedelta(minutes=self.duration_min) if start and self.duration_min else None

    @property
    def day(self) -> date | None:
        """The local departure day."""
        start = self.departs
        return start.date() if start else None

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
    # the cheapest ticket for each departure day we saw, by date: the calendar connections are built from
    by_day: tuple[Ticket, ...] = ()

    def on(self, day: date) -> Ticket | None:
        return next((t for t in self.by_day if t.day == day), None)

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
    days: dict[date, Ticket] = {}
    for t in sorted(tickets, key=lambda t: (t.price, t.transfers)):
        if t.day:
            days.setdefault(t.day, t)
    return RouteFlights(
        cheapest=min(tickets, key=lambda t: t.price),
        direct=min(direct, key=lambda t: t.price) if direct else None,
        fastest=min(timed, key=lambda t: (t.duration_min or 10**6, t.price)),
        by_day=tuple(days[d] for d in sorted(days)),
    )


class TravelpayoutsFlights:
    """Memory, then the fares table, then Aviasales, only for what is still missing.

    A price past its expiry is still served for STALE_FOR while a background fetch replaces it.
    Concurrent lookups of one route share one request, and every request waits for the rate limit.
    """

    def __init__(
        self,
        token: str,
        client: httpx.AsyncClient | None = None,
        timeout_s: float = 8.0,
        store: "FareStore | None" = None,
        network: "Network | None" = None,
        per_minute: float = 300.0,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self._token = token
        self._client = client or httpx.AsyncClient(timeout=timeout_s)
        self._store = store
        self._network = network
        self._clock = clock
        self._cache: dict[FareKey, tuple[datetime, RouteFlights | None]] = {}  # key > (expires, result)
        self._parallel = asyncio.Semaphore(MAX_PARALLEL)
        self._limit = RateLimit(per_minute)
        self._inflight: dict[FareKey, asyncio.Task] = {}
        self._background: set[asyncio.Task] = set()
        self._popular = Popularity()

    async def start(self) -> None:
        """Teaches the route map what the stored fares already showed."""
        if self._store and self._network:
            for origin, destination, airline, at in await self._store.evidence():
                self._network.observe(origin, destination, airline, at)

    async def settle(self) -> None:
        """Waits for the background refreshes: for tests and shutdown."""
        while self._background:
            await asyncio.gather(*list(self._background), return_exceptions=True)

    async def refresh_due(
        self, budget: int, ahead: timedelta = timedelta(minutes=30), at_least: float = 2.0
    ) -> int:
        """Refreshes up to `budget` popular fares that expire within `ahead` (or already have).
        Returns how many were asked. Fares nobody asked for twice lately are left to expire."""
        now = self._clock()
        for key in [k for k, (expires, _) in self._cache.items() if expires <= now - STALE_FOR]:
            del self._cache[key]  # too old to show: the next lookup fetches anyway
        due = [
            k for k, (expires, _) in self._cache.items() if expires <= now + ahead and k not in self._inflight
        ]
        chosen = self._popular.hottest(due, now, at_least)[:budget]
        if chosen:
            await self._fetch(set(chosen))
        return len(chosen)

    async def keep_fresh(self, every: timedelta, budget: int) -> None:
        """Runs refresh_due forever: started at app startup, cancelled at shutdown."""
        while True:
            await asyncio.sleep(every.total_seconds())
            try:
                asked = await self.refresh_due(budget)
                if asked:
                    log.info("Refreshed %d popular fares", asked)
            except Exception:
                log.exception("Fare refresh failed")

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
        found: dict[FareKey, RouteFlights | None] = {}
        stale: set[FareKey] = set()
        for key in keys:
            self._popular.touch(key, now)

        def use(key: FareKey, expires: datetime, result: RouteFlights | None) -> None:
            found[key] = result
            if expires <= now:
                stale.add(key)

        for key in keys:
            hit = self._cache.get(key)
            if hit and hit[0] > now - STALE_FOR:
                use(key, *hit)
        missing = keys - found.keys()
        if missing and self._store:
            stored = await self._store.load(sorted(missing), now)
            self._cache.update(stored)
            for key, hit in stored.items():
                use(key, *hit)
            missing -= stored.keys()
        if stale:
            self._refresh_in_background(stale)
        if missing:
            found.update(await self._fetch(missing))
        return found

    def _refresh_in_background(self, keys: set[FareKey]) -> None:
        task = asyncio.create_task(self._fetch(keys))
        self._background.add(task)
        task.add_done_callback(self._background.discard)

    async def _fetch(self, keys: set[FareKey]) -> dict[FareKey, RouteFlights | None]:
        """Asks Aviasales, sharing a request already on its way for the same key. Failed keys are None."""
        new = sorted(k for k in keys if k not in self._inflight)
        if new:
            task = asyncio.create_task(self._fetch_batch(new))
            for key in new:
                self._inflight[key] = task
            task.add_done_callback(lambda done: self._forget(new, done))
        # shield: a user who leaves must not cancel a request other users are waiting for
        batches = {self._inflight[k] for k in keys}
        results: dict[FareKey, RouteFlights | None] = {}
        for answer in await asyncio.gather(*(asyncio.shield(t) for t in batches)):
            results.update(answer)
        return {k: results.get(k) for k in keys}

    def _forget(self, keys: list[FareKey], task: asyncio.Task) -> None:
        for key in keys:
            if self._inflight.get(key) is task:
                del self._inflight[key]

    async def _fetch_batch(self, keys: list[FareKey]) -> dict[FareKey, RouteFlights | None]:
        answers = await asyncio.gather(*(self._ask(*k) for k in keys))
        now = self._clock()
        fresh: dict[FareKey, tuple[RouteFlights | None, datetime]] = {}
        for key, answer in zip(keys, answers, strict=True):
            if answer is _FAILED:
                continue  # not cached: the next lookup tries again
            fresh[key] = (answer, now + fare_ttl(key[2], now))
            if answer and self._network:
                self._network.observe(key[0], key[1], answer.direct.airline if answer.direct else None, now)
        self._cache.update({key: (expires, answer) for key, (answer, expires) in fresh.items()})
        if fresh and self._store:
            await self._store.save(fresh, now)
        return {key: answer for key, (answer, _) in fresh.items()}

    async def _ask(self, origin: str, destination: str, month: str):
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
            await self._limit.wait()
            async with self._parallel:
                response = await self._client.get(PRICES_URL, params=params)
            response.raise_for_status()
            return summarize(response.json().get("data") or [])
        except (httpx.HTTPError, ValueError, KeyError):
            log.warning("Travelpayouts failed for %s>%s", origin, destination, exc_info=True)
            return _FAILED


_FAILED = object()
