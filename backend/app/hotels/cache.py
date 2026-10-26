"""Hotel offers, cached like flight fares: memory, then the hotel_offers table, then the provider.

One entry per (place, stay): every hotel of the place for one check-in, nights and party, because a booking
site searches a whole region at once. Expiry follows the check-in date (close dates move faster); an expired
entry is still served for STALE_FOR while a background fetch replaces it; concurrent searches of one stay
share one request; stays people keep opening are refreshed before they expire.
"""

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.catalog.catalog import Place
from app.db import hotel_offers
from app.flights.freshness import STALE_FOR, Popularity, fare_ttl
from app.hotels.directory import Listed
from app.hotels.offers import HotelOffers, Offer, StayQuery

log = logging.getLogger(__name__)

Key = tuple[str, str]  # place id, StayQuery.key
Found = dict[str, list[Offer]]


def ttl(stay: StayQuery, now: datetime) -> timedelta:
    return fare_ttl(f"{stay.check_in:%Y-%m}", now)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


class OfferStore:
    """The hotel_offers table. A database failure means «not cached», never an error."""

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]):
        self._sessionmaker = sessionmaker

    async def load(self, key: Key, now: datetime) -> tuple[datetime, Found] | None:
        try:
            async with self._sessionmaker() as db:
                row = (
                    await db.execute(
                        select(hotel_offers).where(
                            hotel_offers.c.place_id == key[0],
                            hotel_offers.c.stay == key[1],
                            hotel_offers.c.expires_at > now - STALE_FOR,
                        )
                    )
                ).first()
        except Exception:
            log.warning("Could not read cached hotel offers", exc_info=True)
            return None
        if row is None:
            return None
        found = {hid: [Offer(**o) for o in offers] for hid, offers in row.offers.items()}
        return _aware(row.expires_at), found

    async def save(
        self, key: Key, found: Found, source: str, fetched_at: datetime, expires_at: datetime
    ) -> None:
        row = {
            "place_id": key[0],
            "stay": key[1],
            "offers": {hid: [o.as_dict() for o in offers] for hid, offers in found.items()},
            "source": source,
            "fetched_at": fetched_at,
            "expires_at": expires_at,
        }
        try:
            async with self._sessionmaker() as db:
                await db.execute(
                    delete(hotel_offers).where(
                        hotel_offers.c.place_id == key[0], hotel_offers.c.stay == key[1]
                    )
                )
                await db.execute(insert(hotel_offers), [row])
                await db.commit()
        except Exception:
            log.warning("Could not save hotel offers for %s", key, exc_info=True)


class CachedOffers:
    def __init__(
        self,
        provider: HotelOffers,
        store: OfferStore | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self._provider = provider
        self._store = store
        self._clock = clock
        self._cache: dict[Key, tuple[datetime, Found]] = {}
        self._asked: dict[Key, tuple[Place, list[Listed], StayQuery]] = {}  # to refresh it later
        self._inflight: dict[Key, asyncio.Task] = {}
        self._background: set[asyncio.Task] = set()
        self._popular = Popularity()

    async def offers(self, place: Place, hotels: list[Listed], stay: StayQuery) -> Found:
        key = (place.id, stay.key)
        now = self._clock()
        self._popular.touch(key, now)
        self._asked[key] = (place, hotels, stay)
        hit = self._cache.get(key)
        if hit is None and self._store:
            hit = await self._store.load(key, now)
            if hit:
                self._cache[key] = hit
        # shortcut: a hotel with no offer makes each search ask again; store the asked ids once a provider skips some
        if hit and hit[0] > now - STALE_FOR and all(h.id in hit[1] for h in hotels):
            if hit[0] <= now:
                self._in_background(key)
            return hit[1]
        return await self._fetch(key)

    async def settle(self) -> None:
        while self._background:
            await asyncio.gather(*list(self._background), return_exceptions=True)

    async def refresh_due(
        self, budget: int, ahead: timedelta = timedelta(minutes=30), at_least: float = 2.0
    ) -> int:
        """Refreshes up to `budget` popular stays that expire within `ahead`, as the flight fares do."""
        now = self._clock()
        due = [
            k for k, (expires, _) in self._cache.items() if expires <= now + ahead and k not in self._inflight
        ]
        chosen = self._popular.hottest(due, now, at_least)[:budget]
        await asyncio.gather(*(self._fetch(k) for k in chosen), return_exceptions=True)
        return len(chosen)

    async def keep_fresh(self, every: timedelta, budget: int) -> None:
        while True:
            await asyncio.sleep(every.total_seconds())
            try:
                if asked := await self.refresh_due(budget):
                    log.info("Refreshed %d popular hotel searches", asked)
            except Exception:
                log.exception("Hotel offer refresh failed")

    def _in_background(self, key: Key) -> None:
        if key in self._inflight:
            return
        task = asyncio.create_task(self._fetch(key))
        self._background.add(task)
        task.add_done_callback(self._background.discard)

    async def _fetch(self, key: Key) -> Found:
        task = self._inflight.get(key)
        if task is None:
            task = asyncio.create_task(self._ask(key))
            self._inflight[key] = task
            task.add_done_callback(
                lambda done: self._inflight.pop(key, None) if self._inflight.get(key) is done else None
            )
        return await asyncio.shield(task)

    async def _ask(self, key: Key) -> Found:
        place, hotels, stay = self._asked[key]
        try:
            found = await self._provider.offers(place, hotels, stay)
        except Exception:
            log.warning("Hotel offers failed for %s", key, exc_info=True)
            stale = self._cache.get(key)
            return stale[1] if stale else {}  # not cached: the next search asks again
        now = self._clock()
        expires = now + ttl(stay, now)
        self._cache[key] = (expires, found)
        if self._store:
            source = next((o.source for offers in found.values() for o in offers), "")
            await self._store.save(key, found, source, now, expires)
        return found
