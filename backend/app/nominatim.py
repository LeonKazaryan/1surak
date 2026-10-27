"""Nominatim's usage policy: one request a second at most, from the whole app.

Hotels (app.hotels.osm) and restaurants (app.plan.live_guide) both ask it; each spacing its own requests would
still make two a second together, and Nominatim blocks an app that does.
"""

import asyncio
import time

GAP_S = 1.1

_lock: asyncio.Lock | None = None
_loop: asyncio.AbstractEventLoop | None = None
_last = 0.0


async def wait_turn() -> None:
    """Returns when this request may go: at least GAP_S after the app's last one."""
    global _lock, _loop, _last
    loop = asyncio.get_running_loop()
    if _lock is None or _loop is not loop:  # a lock belongs to one event loop (tests run several)
        _lock, _loop = asyncio.Lock(), loop
    async with _lock:  # only the spacing: requests themselves may overlap
        await asyncio.sleep(max(0.0, _last + GAP_S - time.monotonic()))
        _last = time.monotonic()
