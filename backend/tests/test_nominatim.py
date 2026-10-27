import asyncio
import time

from app import nominatim


def test_should_space_every_nominatim_request_in_the_app_a_gap_apart(monkeypatch):
    # hotels and restaurants share the one gate: together they stay at Nominatim's one request a second
    monkeypatch.setattr(nominatim, "GAP_S", 0.2)

    async def three() -> float:
        start = time.monotonic()
        await asyncio.gather(nominatim.wait_turn(), nominatim.wait_turn(), nominatim.wait_turn())
        return time.monotonic() - start

    assert asyncio.run(three()) >= 0.4  # the first goes at once, the next two 0.2 s apart
