from dataclasses import dataclass
from datetime import date
from typing import Literal, Protocol

from app.flights.dictionary import City

GroundMode = Literal["train", "bus"]
SOURCES = {
    "tutu": "Туту.ру, расписание поездов",
    "flixbus": "FlixBus, рейсы на дату",
    "yandex": "Яндекс.Расписания",
}
# The line a source's terms require next to its data (Yandex.Rasp: yandex.ru/legal/timetable_api, 2.3.5).
CREDITS = {
    "yandex": {"text": "Данные предоставлены сервисом Яндекс.Расписания", "link": "https://rasp.yandex.ru/"}
}


@dataclass(frozen=True)
class GroundOption:
    """One train or bus: when it leaves and arrives, how long it takes, the cheapest fare and where to buy."""

    mode: GroundMode
    source: str  # tutu | flixbus
    name: str  # «Афросиаб 768Ф», «FlixBus»
    departs: str | None  # «16:49» from a timetable, or an ISO date-time for a dated ride
    arrives: str | None
    minutes: int
    price_rub: int | None
    fare: str | None  # the class the price is for: «сидячий», «купе»
    link: str
    dated: bool = False  # a ride on that very day (FlixBus, Yandex), not a timetable that may skip days
    number: str | None = None  # «123Ф»: the same train from two sources is one train

    def view(self) -> dict:
        view = {
            "mode": self.mode,
            "source": SOURCES.get(self.source, self.source),
            "name": self.name,
            "departs": self.departs,
            "arrives": self.arrives,
            "hours": round(self.minutes / 60 * 2) / 2,
            "price_rub": self.price_rub,
            "fare": self.fare,
            "link": self.link,
            "dated": self.dated,
            "credit": CREDITS.get(self.source),
        }
        return {k: v for k, v in view.items() if v is not None}


def priced_first(options: "tuple[GroundOption, ...] | list[GroundOption]") -> list[GroundOption]:
    """The options with a fare, or all of them when none has one: an unknown fare is not a free ride."""
    priced = [o for o in options if o.price_rub is not None]
    return priced or list(options)


@dataclass(frozen=True)
class GroundRoute:
    """Every train or bus found for one pair of cities."""

    options: tuple[GroundOption, ...]
    picked: GroundOption | None = None  # the one that fits the flights next to it (app.trip.smart)
    wait_min: int = 0  # between the plane and the picked train or bus

    @property
    def cheapest(self) -> GroundOption:
        priced = [o for o in self.options if o.price_rub is not None]
        return min(priced, key=lambda o: (o.price_rub, o.minutes)) if priced else self.fastest

    @property
    def fastest(self) -> GroundOption:
        return min(self.options, key=lambda o: o.minutes)

    @property
    def best(self) -> GroundOption:
        """The one to show: the one picked to fit the flights; else cheap, but a few hundred roubles more for a
        much faster ride is worth it."""
        if self.picked:
            return self.picked
        return min(priced_first(self.options), key=lambda o: (o.price_rub or 0) + 300 * o.minutes / 60)

    def view(self) -> dict:
        view = {**self.best.view(), "options": len(self.options)}
        if self.picked and self.wait_min >= 30:
            view["wait_hours"] = round(self.wait_min / 60 * 2) / 2 or 0.5
        return view


class Ground(Protocol):
    async def route(self, origin: City, destination: City, day: date | None = None) -> GroundRoute | None: ...


class NoGround:
    """No train or bus data: every ground leg stays an estimate by distance."""

    async def route(self, origin: City, destination: City, day: date | None = None) -> GroundRoute | None:
        return None
