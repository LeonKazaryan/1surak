"""How long a cached price is good for, and how fast we may ask Aviasales.

Prices for a trip next week move within hours; for one in three months they hardly move in a day.
A price past its expiry is still shown for a while (STALE_FOR) while a fresh one loads in the background.
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
