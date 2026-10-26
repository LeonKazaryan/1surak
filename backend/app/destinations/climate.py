"""Climate and sea for route-map cities, fetched once from Open-Meteo and kept in the facts table.

Open-Meteo's free tier counts a request for more than two weeks as several calls, so a city gets twelve
two-week windows of 2025, one per month (12 calls), and the sea one probe window, then the other eleven
only when the coast has data. The same adapters as the catalogue turn them into monthly facts; elevation
and «coastal» are kept too, for the kind of trip. One worker fetches in the background at a steady pace,
under the hourly limit, so a search never waits on it: a city joins the search once its facts are in.
"""

import asyncio
import logging
from collections.abc import Callable, Iterable
from dataclasses import replace
from datetime import UTC, datetime

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.destinations import qid
from app.facts import repository
from app.facts.adapters import open_meteo, open_meteo_marine
from app.facts.model import Fact, FactError, normalize
from app.facts.service import resolve_entities
from app.flights import city

log = logging.getLogger(__name__)

YEAR = 2025
WINDOW_FROM, WINDOW_TO = 8, 21  # two weeks in the middle of every month: one call each
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
CALLS_PER_MINUTE = 60  # well under the free 600 a minute and 5,000 an hour
NOW_GAP_S = 0.05  # a search's few cities at once: a burst well inside 600 a minute
NOW_TIMEOUT_S = 15.0
BURST = 20  # requests in flight at once
SOURCE = "open-meteo-2025"


def windows() -> list[tuple[str, str]]:
    return [(f"{YEAR}-{m:02d}-{WINDOW_FROM:02d}", f"{YEAR}-{m:02d}-{WINDOW_TO:02d}") for m in range(1, 13)]


def merged(payloads: list[dict], variables: list[str]) -> dict:
    """Twelve window answers as one payload, the shape the catalogue's adapters read."""
    daily: dict[str, list] = {"time": []}
    for name in variables:
        daily[name] = []
    for p in payloads:
        part = p.get("daily") or {}
        for key in daily:
            daily[key] += part.get(key) or [None] * len(part.get("time") or [])
    units = next((p.get("daily_units") for p in payloads if p.get("daily_units")), {})
    return {
        "daily": daily,
        "daily_units": units,
        "elevation": next((p.get("elevation") for p in payloads), None),
    }


def _marker(code: str, attribute: str, value, unit: str | None, fetched_at: datetime) -> Fact:
    return normalize(
        Fact(
            entity_type="place",
            entity_id=qid(code),
            attribute=attribute,
            value=value,
            unit=unit,
            source=SOURCE,
            source_url=ARCHIVE_URL,
            source_tier="official",
            kind="real",
            fetched_at=fetched_at,
        )
    )


class ClimateFetcher:
    def __init__(
        self,
        sessionmaker: async_sessionmaker[AsyncSession],
        client: httpx.AsyncClient | None = None,
        per_minute: float = CALLS_PER_MINUTE,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self._sessionmaker = sessionmaker
        self._client = client or httpx.AsyncClient(timeout=30)
        self._gap = 60 / per_minute
        self._clock = clock
        # (priority, order, code): a city someone searched from jumps the start-up prefetch
        self._queue: asyncio.PriorityQueue[tuple[int, int, str]] = asyncio.PriorityQueue()
        self._order = 0
        self._queued: set[str] = set()
        self._worker: asyncio.Task | None = None
        self._burst = asyncio.Semaphore(BURST)
        self.fetched = 0

    async def missing(self, codes: Iterable[str]) -> list[str]:
        """The cities with no climate in the facts table yet."""
        codes = [c for c in dict.fromkeys(codes) if city(c)]
        if not codes:
            return []
        async with self._sessionmaker() as db:
            facts = await resolve_entities(db, "place", [qid(c) for c in codes], self._clock())
        return [c for c in codes if not any(a == "air_max" for a, _ in facts[qid(c)])]

    async def ensure(self, codes: Iterable[str], urgent: bool = True) -> int:
        """Queues the cities that still need their climate; returns how many are waiting.
        `urgent` (a search) goes before the background prefetch (urgent=False)."""
        for code in await self.missing(codes):
            if code not in self._queued:
                self._queued.add(code)
                self._order += 1
                self._queue.put_nowait((0 if urgent else 1, self._order, code))
        if self._worker is None or self._worker.done():
            self._worker = asyncio.create_task(self._work())
        return self._queue.qsize()

    async def drain(self) -> None:
        """Waits for the queue: for tests and the seed script."""
        if self._worker:
            await self._queue.join()

    def stop(self) -> None:
        if self._worker:
            self._worker.cancel()

    async def _work(self) -> None:
        while True:
            _, _, code = await self._queue.get()
            try:
                await self.fetch(code)
                self.fetched += 1
            except Exception:
                log.warning("Climate for %s failed; it is asked again on a later search", code, exc_info=True)
            finally:
                self._queued.discard(code)
                self._queue.task_done()

    async def fetch_now(self, codes: list[str], timeout_s: float = NOW_TIMEOUT_S) -> int:
        """Fetches these cities right away, side by side, for a search that would otherwise show nothing new;
        whatever does not finish in time goes to the background queue. Returns how many arrived."""
        tasks = [asyncio.create_task(self.fetch(code, gap=NOW_GAP_S)) for code in codes]
        done, pending = await asyncio.wait(tasks, timeout=timeout_s) if tasks else (set(), set())
        for task in pending:
            task.cancel()
        if pending:
            await self.ensure(codes)
        return sum(1 for task in done if not task.exception())

    async def _many(self, url: str, params: list[dict], gap: float | None) -> list[dict]:
        """Several windows: one after another at the background pace, or side by side for a search."""
        if gap is None:
            return [await self._get(url, p) for p in params]
        return list(await asyncio.gather(*(self._get(url, p, gap) for p in params)))

    async def _get(self, url: str, params: dict, gap: float | None = None) -> dict:
        await asyncio.sleep(self._gap if gap is None else gap)  # a steady pace keeps the free tier's limits
        async with self._burst:  # a search's cities side by side, but never more than this many at once
            response = await self._client.get(url, params=params)
        response.raise_for_status()
        return response.json()

    async def fetch(self, code: str, gap: float | None = None) -> list[Fact]:
        """Every fact for one city: monthly air and rain, sea when it has one, elevation, coastal."""
        c = city(code)
        now = self._clock()
        point = {"latitude": c.lat, "longitude": c.lon, "timezone": "auto"}
        air_vars = ["temperature_2m_max", "temperature_2m_min", "precipitation_sum"]
        air = await self._many(
            ARCHIVE_URL,
            [{**point, "start_date": a, "end_date": b, "daily": ",".join(air_vars)} for a, b in windows()],
            gap,
        )
        payload = merged(air, air_vars)
        facts = [_retag(f) for f in open_meteo.monthly_climate(qid(code), payload, now)]
        if payload.get("elevation") is not None:
            facts.append(_marker(code, "elevation", round(payload["elevation"]), "m", now))
        sea = await self._sea(point, now, code, gap)
        facts += sea
        facts.append(_marker(code, "coastal", bool(sea), None, now))
        async with self._sessionmaker() as db:
            await repository.save_facts(db, facts)
            await db.commit()
        return facts

    async def _sea(self, point: dict, now: datetime, code: str, gap: float | None = None) -> list[Fact]:
        variable = open_meteo_marine.VARIABLE
        spots = windows()
        probe = await self._get(
            MARINE_URL, {**point, "start_date": spots[6][0], "end_date": spots[6][1], "daily": variable}, gap
        )
        if not any(v is not None for v in (probe.get("daily") or {}).get(variable) or []):
            return []  # inland: no sea, and no eleven more calls
        rest = await self._many(
            MARINE_URL,
            [
                {**point, "start_date": a, "end_date": b, "daily": variable}
                for i, (a, b) in enumerate(spots)
                if i != 6
            ],
            gap,
        )
        payload = merged([*rest[:6], probe, *rest[6:]], [variable])
        try:
            return [_retag(f) for f in open_meteo_marine.monthly_sea_temp(qid(code), payload, now)]
        except FactError:
            return []


def _retag(fact: Fact) -> Fact:
    """One year of two-week windows is not the catalogue's five-year normal: its own source says so."""
    return replace(fact, source=f"{fact.source}-{YEAR}")
