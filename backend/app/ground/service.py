import asyncio
import logging
from datetime import date

from app.flights.dictionary import City
from app.ground.flixbus import FlixBuses
from app.ground.model import Ground, GroundRoute, NoGround
from app.ground.tutu import TutuTrains

log = logging.getLogger(__name__)


class GroundTransport:
    """Trains from Tutu where its railways run, buses from FlixBus (when on), one list of options."""

    def __init__(self, trains: TutuTrains | None = None, buses: FlixBuses | None = None):
        self._trains = trains
        self._buses = buses

    async def route(self, origin: City, destination: City, day: date | None = None) -> GroundRoute | None:
        asks = []
        if self._trains and self._trains.covers(origin) and self._trains.covers(destination):
            asks.append(self._trains.route(origin, destination))
        elif self._buses:  # FlixBus does not run on the Soviet gauge: ask it only where Tutu cannot answer
            asks.append(self._buses.route(origin, destination, day))
        answers = await asyncio.gather(*asks, return_exceptions=True)
        for problem in (a for a in answers if isinstance(a, Exception)):
            log.warning("A train or bus source failed: %r", problem)  # the hop stays an estimate
        found = [r for r in answers if isinstance(r, GroundRoute)]
        options = tuple(o for r in found for o in r.options)
        return GroundRoute(options) if options else None


# Set once at startup (app.main), read wherever a route is priced. Tests and a disabled setting keep NoGround,
# so no test ever calls a real timetable.
_transport: Ground = NoGround()


def configure(ground: Ground) -> None:
    global _transport
    _transport = ground


def transport() -> Ground:
    return _transport
