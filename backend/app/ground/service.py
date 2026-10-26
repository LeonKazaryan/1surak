import asyncio
import logging
import re
from dataclasses import replace
from datetime import date

from app.flights.dictionary import City
from app.ground.flixbus import FlixBuses
from app.ground.model import Ground, GroundOption, GroundRoute, NoGround
from app.ground.tutu import TutuTrains
from app.ground.yandex import YandexRasp

log = logging.getLogger(__name__)


def _same(number: str | None) -> str:
    """One key for one train: «013*Ж» (Tutu) and «014Ж» (Yandex) are the same train, since a train's odd number
    turns even (or back) where it changes direction on the way; marks like «*» do not count."""
    plain = re.sub(r"[^0-9a-zа-яё]", "", (number or "").casefold())
    digits, letters = re.match(r"(\d*)(.*)", plain).groups()
    return f"{(int(digits) + 1) // 2 if digits else ''}{letters}"


def merged(trains: tuple[GroundOption, ...], rides: tuple[GroundOption, ...]) -> list[GroundOption]:
    """Tutu's trains with Yandex's rides. A train both know takes Yandex's times on the trip's day (and its
    fare, when it has one) with Tutu's name and link to buy; Yandex adds what Tutu does not list: buses,
    suburban trains, «Ласточки»."""
    found = list(trains)
    known = {_same(o.number): i for i, o in enumerate(found) if o.number}
    for ride in rides:
        i = known.get(_same(ride.number)) if ride.number else None
        if i is None:
            found.append(ride)
        elif ride.dated:  # a typical day's copy of a train Tutu has adds nothing
            same, priced = found[i], ride.price_rub is not None
            found[i] = replace(
                ride,
                name=same.name,
                link=same.link,
                price_rub=ride.price_rub if priced else same.price_rub,
                fare=ride.fare if priced else same.fare,
            )
    return found


class GroundTransport:
    """Trains from Tutu where its railways run, trains and buses from Yandex.Rasp (with a key) on the same
    network, buses from FlixBus (when on) elsewhere: one list of options."""

    def __init__(
        self,
        trains: TutuTrains | None = None,
        buses: FlixBuses | None = None,
        rasp: YandexRasp | None = None,
    ):
        self._trains = trains
        self._buses = buses
        self._rasp = rasp

    async def route(self, origin: City, destination: City, day: date | None = None) -> GroundRoute | None:
        tutu = bool(self._trains and self._trains.covers(origin) and self._trains.covers(destination))
        asks = {}
        if tutu:
            asks["trains"] = self._trains.route(origin, destination)
        if self._rasp and self._rasp.covers(origin) and self._rasp.covers(destination):
            asks["rasp"] = self._rasp.route(origin, destination, day)
        if (
            self._buses and not tutu
        ):  # FlixBus does not run on the Soviet gauge: ask it only where Tutu cannot
            asks["buses"] = self._buses.route(origin, destination, day)
        answers = dict(zip(asks, await asyncio.gather(*asks.values(), return_exceptions=True), strict=True))
        for name, problem in answers.items():
            if isinstance(problem, Exception):
                log.warning(
                    "Ground source %s failed: %s", name, type(problem).__name__
                )  # the hop stays an estimate

        def got(name: str) -> tuple[GroundOption, ...]:
            answer = answers.get(name)
            return answer.options if isinstance(answer, GroundRoute) else ()

        options = (*merged(got("trains"), got("rasp")), *got("buses"))
        return GroundRoute(options) if options else None


# Set once at startup (app.main), read wherever a route is priced. Tests and a disabled setting keep NoGround,
# so no test ever calls a real timetable.
_transport: Ground = NoGround()


def configure(ground: Ground) -> None:
    global _transport
    _transport = ground


def transport() -> Ground:
    return _transport
