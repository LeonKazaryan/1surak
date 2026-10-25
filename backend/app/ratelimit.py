"""How often one client may start a chat turn or a price refresh: each one spends LLM credits or API quota."""

import time
from collections import defaultdict, deque
from collections.abc import Callable

from fastapi import HTTPException

WINDOW_S = 60


class RateLimit:
    # shortcut: kept in this process and keyed by the socket address, so behind a proxy all users share one
    # key; set the limit at the proxy or in Redis when the app runs behind one
    def __init__(self, per_minute: int, clock: Callable[[], float] = time.monotonic):
        self._per_minute = per_minute
        self._clock = clock
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def hit(self, client: str) -> None:
        if self._per_minute <= 0:
            return
        now = self._clock()
        hits = self._hits[client]
        while hits and now - hits[0] >= WINDOW_S:
            hits.popleft()
        if len(hits) >= self._per_minute:
            raise HTTPException(
                status_code=429,
                detail="Too many requests, try again in a minute",
                headers={"Retry-After": str(WINDOW_S)},
            )
        hits.append(now)
