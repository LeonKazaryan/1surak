"""Answers found once and kept: visa fees, taxi fares, city guides.

Each kind of answer is found slowly (a web search and a model, open data APIs) and changes slowly, so it is
kept: in memory, then in the lookups table, and only then found again. Concurrent asks for one key share one
find; finds run a few at a time; a found answer lives `found_ttl`, «nothing found» `missed_ttl`, and a failure
(a rate limit, an outage) only FAILED_TTL in memory, so it is tried again soon but not hammered.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable, Iterable
from datetime import UTC, datetime, timedelta
from typing import Generic, TypeVar

from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import lookups

log = logging.getLogger(__name__)

V = TypeVar("V")
FAILED_TTL = timedelta(minutes=10)


class LookupStore:
    """The lookups table. A database failure means «not cached», never an error."""

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]):
        self._sessionmaker = sessionmaker

    async def load(self, kind: str, keys: list[str]) -> dict[str, tuple[datetime, dict | None]]:
        try:
            async with self._sessionmaker() as db:
                rows = (
                    await db.execute(select(lookups).where(lookups.c.kind == kind, lookups.c.key.in_(keys)))
                ).all()
        except Exception:
            log.warning("Could not read cached %s", kind, exc_info=True)
            return {}
        return {
            row.key: (
                row.checked_at if row.checked_at.tzinfo else row.checked_at.replace(tzinfo=UTC),
                row.value,
            )
            for row in rows
        }

    async def save(self, kind: str, key: str, value: dict | None, at: datetime) -> None:
        try:
            async with self._sessionmaker() as db:
                await db.execute(delete(lookups).where(lookups.c.kind == kind, lookups.c.key == key))
                await db.execute(insert(lookups).values(kind=kind, key=key, value=value, checked_at=at))
                await db.commit()
        except Exception:
            log.warning("Could not cache %s for %s", kind, key, exc_info=True)


class Lookups(Generic[V]):
    def __init__(
        self,
        kind: str,
        find: Callable[[str], Awaitable[V | None]],
        store: LookupStore | None,
        encode: Callable[[V], dict],
        decode: Callable[[dict], V],
        found_ttl: timedelta,
        missed_ttl: timedelta,
        at_once: int = 3,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self.kind = kind
        self._find = find
        self._store = store
        self._encode, self._decode = encode, decode
        self._found_ttl, self._missed_ttl = found_ttl, missed_ttl
        self._now = now
        self._memory: dict[str, tuple[datetime, V | None, timedelta]] = {}
        self._running: dict[str, asyncio.Task] = {}
        self._turn = asyncio.Semaphore(at_once)
        self._background: set[asyncio.Task] = set()

    def _remember(self, key: str, at: datetime, value: V | None, ttl: timedelta | None = None) -> None:
        self._memory[key] = (at, value, ttl or (self._found_ttl if value is not None else self._missed_ttl))

    def _fresh(self, key: str) -> bool:
        entry = self._memory.get(key)
        return bool(entry) and self._now() - entry[0] < entry[2]

    def ttl_of(self, key: str) -> timedelta | None:
        entry = self._memory.get(key)
        return entry[2] if entry else None

    def known(self, key: str) -> V | None:
        """The answer already in memory, without waiting."""
        return self._memory[key][1] if self._fresh(key) else None

    async def _load(self, keys: list[str]) -> None:
        if not self._store or not keys:
            return
        for key, (at, raw) in (await self._store.load(self.kind, keys)).items():
            value = self._decode(raw) if raw else None
            if self._now() - at < (self._found_ttl if value is not None else self._missed_ttl):
                self._remember(key, at, value)

    async def warm(self, keys: Iterable[str]) -> None:
        """The cached answers of these keys into memory (one query), and a find started for every other one:
        by the time someone needs it, it is usually there."""
        wanted = list(dict.fromkeys(k for k in keys if k))
        await self._load([k for k in wanted if not self._fresh(k) and k not in self._running])
        for key in wanted:
            if not self._fresh(key) and key not in self._running:
                task = asyncio.create_task(self.get(key))
                self._background.add(task)
                task.add_done_callback(self._background.discard)

    async def get(self, key: str, wait_s: float | None = None) -> V | None:
        """The answer for this key: from memory or the table, else found (once, however many ask). With
        `wait_s`, None when it takes longer; the find goes on and lands in the cache."""
        if self._fresh(key):
            return self._memory[key][1]
        if key not in self._running:
            await self._load([key])
            if self._fresh(key):
                return self._memory[key][1]
        task = self._running.get(key)
        if task is None:
            task = self._running[key] = asyncio.create_task(self._lookup(key))
            task.add_done_callback(lambda _: self._running.pop(key, None))
        try:
            return await asyncio.wait_for(asyncio.shield(task), wait_s)
        except TimeoutError:
            return None

    async def get_many(self, keys: Iterable[str], wait_s: float | None = None) -> dict[str, V | None]:
        wanted = list(dict.fromkeys(k for k in keys if k))
        found = await asyncio.gather(*(self.get(k, wait_s) for k in wanted))
        return dict(zip(wanted, found, strict=True))

    async def _lookup(self, key: str) -> V | None:
        async with self._turn:
            try:
                value = await self._find(key)
            except Exception:
                log.warning("Finding %s for %s failed", self.kind, key, exc_info=True)
                self._remember(key, self._now(), None, FAILED_TTL)
                return None
        at = self._now()
        self._remember(key, at, value)
        if self._store:
            await self._store.save(self.kind, key, self._encode(value) if value is not None else None, at)
        return value

    async def settle(self) -> None:
        for task in list(self._background):
            task.cancel()
