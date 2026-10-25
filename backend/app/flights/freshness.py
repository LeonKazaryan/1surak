"""How long a cached price is good for, and how fast we may ask Aviasales.

Prices for a trip next week move within hours; for one in three months they hardly move in a day.
A price past its expiry is still shown for a while (STALE_FOR) while a fresh one loads in the background.
Routes people keep asking for are refreshed before they expire (Popularity + the client's refresher),
so a popular search never waits on Aviasales.
"""

import asyncio
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

SOON = timedelta(hours=3)  # departure within two weeks, or «the nearest dates»
MONTHS_OUT = timedelta(hours=12)  # within two months
LATER = timedelta(hours=24)
STALE_FOR = timedelta(days=2)  # after that an old price is worse than waiting a second for a new one


def fare_ttl(month: str, now: datetime) -> timedelta:
    """`month` is "YYYY-MM", or "" for the nearest dates."""
    if not month:
        return SOON
    year, number = map(int, month.split("-"))
    days = (datetime(year, number, 1, tzinfo=UTC) - now).days
    if days < 14:
        return SOON
    return MONTHS_OUT if days < 60 else LATER


class RateLimit:
    """Token bucket: up to `burst` calls at once, then `per_minute` on average."""

    def __init__(self, per_minute: float, burst: int = 20, clock: Callable[[], float] = time.monotonic):
        self._rate = per_minute / 60
        self._burst = burst
        self._tokens = float(burst)
        self._clock = clock
        self._at = clock()
        self._lock = asyncio.Lock()

    async def wait(self) -> None:
        async with self._lock:  # one waiter at a time, so calls go out in order
            now = self._clock()
            self._tokens = min(self._burst, self._tokens + (now - self._at) * self._rate)
            self._at = now
            if self._tokens < 1:
                await asyncio.sleep((1 - self._tokens) / self._rate)
                self._at = self._clock()
                self._tokens = 1
            self._tokens -= 1


HALF_LIFE = timedelta(hours=6)  # a lookup counts half as much six hours later


class Popularity:
    """How often each key was asked for lately: every lookup adds 1, and the total halves every HALF_LIFE."""

    def __init__(self):
        self._scores: dict = {}  # key > (score, at)

    def touch(self, key, now: datetime) -> None:
        self._scores[key] = (self.score(key, now) + 1, now)

    def score(self, key, now: datetime) -> float:
        found = self._scores.get(key)
        if found is None:
            return 0.0
        value, at = found
        return value * 0.5 ** ((now - at) / HALF_LIFE)

    def hottest(self, keys, now: datetime, at_least: float) -> list:
        """`keys` ordered by score, only those with `at_least`; forgets keys that cooled down to nothing."""
        for key in [k for k in self._scores if self.score(k, now) < 0.05]:
            del self._scores[key]
        scored = [(self.score(k, now), k) for k in keys]
        return [k for value, k in sorted(scored, key=lambda x: -x[0]) if value >= at_least]
