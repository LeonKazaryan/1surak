"""Multi-city trips: price every leg, and when the order is open, try every order of the stops.

Each leg is a separate one-way ticket. Fares come from Flights (cached, one request per route); where
Aviasales has no price, the route map says whether a direct flight exists and how long it takes.
A catalogue place without an airport (Suzdal, Anapa) is reached by train, from Moscow only.

Plans are ranked by a score in roubles: ticket price + time + transfers, weighted by the preference.
"""

import asyncio
import itertools
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Literal

from app.catalog.catalog import RAIL_ORIGIN, Catalog
from app.flights.client import Flights, RouteFlights, Ticket
from app.flights.dictionary import City, cities, city
from app.flights.network import Network

Preference = Literal["cheapest", "balanced", "fastest"]
# (roubles one hour of travel is worth, roubles one transfer is worth)
WEIGHTS: dict[str, tuple[int, int]] = {
    "cheapest": (100, 500),
    "balanced": (1_500, 3_000),
    "fastest": (6_000, 6_000),
}
UNPRICED_RUB = 100_000  # a leg we have no price for ranks as an expensive one, never as a free one
MAX_OPEN_STOPS = 5  # 5! = 120 orders and 30 fares; more would be slow for a chat answer
TOP_PLANS = 3

Mode = Literal["flight", "train", "none"]


@dataclass(frozen=True)
class Stop:
    name: str
    code: str | None  # city code; None for a place reached only by train
    train_min: int | None = None  # train from RAIL_ORIGIN, catalogue places only

    @staticmethod
    def of_city(found: City) -> "Stop":
        return Stop(found.name, found.code)


def resolve_stop(name: str, catalog: Catalog) -> Stop | None:
    """A catalogue place by exact id or name, then any city with an airport, then a catalogue name part."""
    needle = name.strip().casefold()
    exact = next((p for p in catalog.places if needle in (p.id, p.name.casefold())), None)
    if exact is None:
        found = city(name) or next((c for c in cities().values() if c.name.casefold() == needle), None)
        if found:
            return Stop.of_city(found)
        exact = catalog.find(name)
    if exact is None:
        return None
    airport = city(exact.airport) if exact.airport else None
    return Stop(exact.name, airport.code if airport else None, exact.train_min)


@dataclass(frozen=True)
class Leg:
    origin: Stop
    destination: Stop
    month: int | None
    day: date | None
    mode: Mode
    score: float
    ticket: Ticket | None = None
    route: RouteFlights | None = None
    minutes: int | None = None  # the ticket's, the train's, or the map's estimate
    direct_on_map: bool = False
    train_min: int | None = None  # a train alternative to a flight

    @property
    def price(self) -> int | None:
        return self.ticket.price if self.ticket else None

    def view(self) -> dict:
        view: dict = {"from": self.origin.name, "to": self.destination.name, "mode": self.mode}
        if self.day:
            view["date"] = self.day.isoformat()
        if self.ticket:
            view["ticket"] = self.ticket.view()
            if self.route and self.route.direct and self.route.direct is not self.ticket:
                view["direct_option"] = self.route.direct.view()
        elif self.mode == "flight":
            view["ticket"] = None
            view["direct_on_map"] = self.direct_on_map
        if self.minutes is not None and not self.ticket:
            view["est_hours"] = _hours(self.minutes)
        if self.train_min is not None:
            view["train_hours"] = _hours(self.train_min)
        return view


@dataclass
class Plan:
    stops: tuple[Stop, ...]
    legs: list[Leg] = field(default_factory=list)

    @property
    def score(self) -> float:
        return sum(leg.score for leg in self.legs)

    @property
    def possible(self) -> bool:
        return all(leg.mode != "none" for leg in self.legs)

    def view(self) -> dict:
        priced = [leg.price for leg in self.legs if leg.price is not None]
        minutes = [leg.minutes for leg in self.legs if leg.minutes is not None]
        return {
            "order": [s.name for s in self.stops],
            "total_price_rub": sum(priced) if priced else None,
            "unpriced_legs": sum(1 for leg in self.legs if leg.mode == "flight" and leg.price is None),
            "impossible_legs": [
                f"{leg.origin.name} → {leg.destination.name}" for leg in self.legs if leg.mode == "none"
            ],
            "travel_hours": _hours(sum(minutes)) if minutes else None,
            "legs": [leg.view() for leg in self.legs],
        }


FareKey = tuple[str, str, int | None]  # origin city, destination city, month


def _hours(minutes: int) -> float:
    return round(minutes / 60 * 2) / 2


def _ticket_score(ticket: Ticket, preference: str) -> float:
    per_hour, per_transfer = WEIGHTS[preference]
    return ticket.price + per_hour * ticket.duration_min / 60 + per_transfer * ticket.transfers


def best_ticket(route: RouteFlights, preference: str) -> Ticket:
    options = {id(t): t for t in (route.cheapest, route.direct, route.fastest) if t}
    return min(options.values(), key=lambda t: (_ticket_score(t, preference), t.price))


def _train(origin: Stop, destination: Stop) -> int | None:
    if origin.code == RAIL_ORIGIN and destination.train_min:
        return destination.train_min
    if destination.code == RAIL_ORIGIN and origin.train_min:
        return origin.train_min
    return None


def make_leg(
    origin: Stop,
    destination: Stop,
    month: int | None,
    day: date | None,
    fares: dict[FareKey, RouteFlights | None],
    network: Network,
    preference: str,
) -> Leg:
    per_hour, _ = WEIGHTS[preference]
    where = (origin, destination, month, day)
    train = _train(origin, destination)
    if origin.code and destination.code:
        route = fares.get((origin.code, destination.code, month))
        if route:
            ticket = best_ticket(route, preference)
            score = _ticket_score(ticket, preference)
            return Leg(
                *where,
                mode="flight",
                score=score,
                ticket=ticket,
                route=route,
                minutes=ticket.duration_min,
                direct_on_map=route.direct is not None,
                train_min=train,
            )
        link = network.link(origin.code, destination.code)
        minutes = link.minutes if link else network.estimate(origin.code, destination.code)
        # no direct link on the map: a transfer is likely, so the estimate gets two extra hours
        minutes = minutes if link or minutes is None else minutes + 120
        score = UNPRICED_RUB + per_hour * (minutes or 0) / 60
        return Leg(
            *where,
            mode="flight",
            score=score,
            minutes=minutes,
            direct_on_map=link is not None,
            train_min=train,
        )
    if train:
        # train fares are unknown too, but cheaper than a flight as a rule: rank between priced and unpriced
        return Leg(*where, mode="train", score=UNPRICED_RUB / 2 + per_hour * train / 60, minutes=train)
    return Leg(*where, mode="none", score=float("inf"))


@dataclass(frozen=True)
class Request:
    home: Stop
    stops: tuple[Stop, ...]
    order_fixed: bool = True
    return_home: bool = True
    month: int | None = None
    date_from: date | None = None
    nights: tuple[int, ...] = ()  # per stop, in the order of `stops`; one number applies to all
    preference: Preference = "balanced"

    def nights_at(self, stop: Stop) -> int:
        if not self.nights:
            return 0
        if len(self.nights) == 1:
            return self.nights[0]
        index = self.stops.index(stop)
        return self.nights[index] if index < len(self.nights) else self.nights[-1]


def _orders(request: Request) -> list[tuple[Stop, ...]]:
    if request.order_fixed or len(request.stops) < 2:
        return [request.stops]
    return list(itertools.permutations(request.stops))


def _schedule(request: Request, order: tuple[Stop, ...]) -> list[tuple[Stop, Stop, int | None, date | None]]:
    """The legs of one order with the month (and day, when the trip has a start date) each one flies."""
    path = [request.home, *order, *([request.home] if request.return_home else [])]
    legs, day = [], request.date_from
    for i, (a, b) in enumerate(itertools.pairwise(path)):
        if day and i:
            day = day + timedelta(days=request.nights_at(a))
        legs.append((a, b, day.month if day else request.month, day))
    return legs


async def _fares(flights: Flights, keys: set[FareKey]) -> dict[FareKey, RouteFlights | None]:
    """One Flights.routes call per (origin, month), all at once."""
    groups: dict[tuple[str, int | None], list[str]] = {}
    for origin, destination, month in keys:
        groups.setdefault((origin, month), []).append(destination)
    answers = await asyncio.gather(*(flights.routes(o, sorted(ds), m) for (o, m), ds in groups.items()))
    return {
        (o, d, m): found
        for ((o, m), _), answer in zip(groups.items(), answers, strict=True)
        for d, found in answer.items()
    }


async def plan(request: Request, flights: Flights, network: Network) -> list[Plan]:
    """The best plans first: one for a fixed order, up to TOP_PLANS orders for an open one."""
    schedules = {order: _schedule(request, order) for order in _orders(request)}
    keys = {
        (a.code, b.code, m)
        for legs in schedules.values()
        for a, b, m, _ in legs
        if a.code and b.code and a != b
    }
    fares = await _fares(flights, keys)
    plans = []
    for order, legs in schedules.items():
        result = Plan(order)
        result.legs = [make_leg(a, b, m, d, fares, network, request.preference) for a, b, m, d in legs]
        plans.append(result)
    plans.sort(key=lambda p: p.score)
    return plans[:TOP_PLANS]
