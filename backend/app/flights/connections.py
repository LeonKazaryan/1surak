"""Cheaper by changing planes yourself: A → hub → B on two separate tickets.

The route map picks the hubs before we pay for a single request: cities with a direct flight from A and a
direct flight on to B, that add little distance. Then the two calendars (cheapest ticket per day) are
matched so the second flight leaves 3 to 30 hours after the first lands: two prices from different days
of the month would be a plan nobody can fly.
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta

from app.flights.client import RouteFlights, Ticket
from app.flights.dictionary import City, city, city_code, distance_km
from app.flights.network import Network

MAX_DETOUR = 1.35  # the hub may add up to 35% to the distance
HUBS_PER_LEG = 3
MIN_LAYOVER = timedelta(hours=3)  # separate tickets: collect bags, check in again
MAX_LAYOVER = timedelta(hours=30)  # one night in the hub at most


def hubs(network: Network, origin: str, destination: str, limit: int = HUBS_PER_LEG) -> list[str]:
    """The best hubs for origin → destination, by the distance they add; doubtful links rank lower."""
    o, d = city_code(origin), city_code(destination)
    a, b = city(o), city(d)
    if a is None or b is None or o == d:
        return []
    direct_km = max(distance_km(a, b), 1.0)
    ranked = []
    for first in network.links_from(o):
        hub = first.destination.code
        second = network.link(hub, d) if hub != d else None
        if second is None:
            continue
        detour = (first.km + second.km) / direct_km
        if detour > MAX_DETOUR:
            continue
        doubt = sum(0.15 for link in (first, second) if link.status == "doubtful")
        ranked.append((detour + doubt, hub))
    return [hub for _, hub in sorted(ranked)[:limit]]


@dataclass(frozen=True)
class Connection:
    hub: City
    first: Ticket
    second: Ticket

    @property
    def price(self) -> int:
        return self.first.price + self.second.price

    @property
    def layover(self) -> timedelta:
        return self.second.departs - self.first.arrives

    @property
    def minutes(self) -> int:
        return round((self.second.arrives - self.first.departs).total_seconds() / 60)

    @property
    def transfers(self) -> int:
        return self.first.transfers + self.second.transfers + 1

    def view(self) -> dict:
        return {
            "via": self.hub.name,
            "price_rub": self.price,
            "hours": round(self.minutes / 60 * 2) / 2,
            "layover_hours": round(self.layover.total_seconds() / 3600 * 2) / 2,
            "separate_tickets": True,
            "tickets": [self.first.view(), self.second.view()],
        }


def _calendar(route: RouteFlights) -> tuple[Ticket, ...]:
    return route.by_day or (route.cheapest,)


def connect(
    hub: City,
    first: RouteFlights,
    second: RouteFlights,
    score: Callable[[int, int, int], float],
    day: date | None = None,
) -> Connection | None:
    """The best pair of tickets that can actually be flown in a row. `score(price, minutes, transfers)`.
    With `day`, the first flight leaves that day or the next."""
    best: tuple[float, Connection] | None = None
    for one in _calendar(first):
        if one.arrives is None or (day and one.day not in (day, day + timedelta(days=1))):
            continue
        for two in _calendar(second):
            if two.departs is None or two.arrives is None:
                continue
            if not MIN_LAYOVER <= two.departs - one.arrives <= MAX_LAYOVER:
                continue
            found = Connection(hub, one, two)
            value = score(found.price, found.minutes, found.transfers)
            if best is None or value < best[0]:
                best = (value, found)
    return best[1] if best else None


GUIDE_HUBS = 3  # big airports tried at each end when nobody has a fare for a route on any day
MAX_GUIDE_DETOUR = 1.6
GUIDE_LAYOVER_MIN = 180  # a change of planes on separate tickets, counted into the time


@dataclass(frozen=True)
class HubGuide:
    """Two tickets through a hub that stand in for a route nobody has a fare for: a price to plan with."""

    hub: City
    first: Ticket
    second: Ticket

    @property
    def price(self) -> int:
        return self.first.price + self.second.price

    @property
    def ticket(self) -> Ticket:
        """Both flights as one guide ticket: the first one's departure and airline, both prices and times."""
        a, b = self.first, self.second
        return Ticket(
            a.origin_airport,
            b.destination_airport,
            a.airline,
            a.flight_number,
            a.departure_at,
            self.price,
            a.transfers + b.transfers + 1,
            a.duration_min + b.duration_min + GUIDE_LAYOVER_MIN,
            a.link,
        )

    @property
    def flights(self) -> RouteFlights:
        return RouteFlights(cheapest=self.ticket, direct=None, fastest=self.ticket)

    @property
    def where(self) -> str:
        return self.hub.name_in or self.hub.name  # «в Дубае»


def _big(network: Network, codes: list[str], limit: int) -> list[str]:
    """The best connected of these airports: a big hub has fares to almost anywhere."""
    return sorted(dict.fromkeys(codes), key=lambda c: -len(network.links_from(c)))[:limit]


def guide_hubs(network: Network, origin: str, destination: str) -> list[str]:
    """Where to change for a route nobody has a fare for: the big airports that fly to the destination (for
    Harare: Johannesburg, Addis Ababa, Nairobi) and the ones the origin flies to (for Astana: Istanbul,
    Abu Dhabi), within a sane detour. Each half is priced by real fares, transfers and all."""
    o, d = city_code(origin), city_code(destination)
    a, b = city(o), city(d)
    if a is None or b is None or o == d:
        return []
    direct_km = max(distance_km(a, b), 1.0)
    near_end = _big(network, [link.origin.code for link in network.links_to(d)], GUIDE_HUBS)
    near_start = _big(network, [link.destination.code for link in network.links_from(o)], GUIDE_HUBS)
    return [
        h
        for h in dict.fromkeys([*near_end, *near_start])
        if h not in (o, d)
        and (c := city(h))
        and (distance_km(a, c) + distance_km(c, b)) / direct_km <= MAX_GUIDE_DETOUR
    ]


async def through_hub(origin: str, destination: str, flights, network: Network) -> HubGuide | None:
    """No fare for origin → destination on any day (Astana → Harare): the cheapest pair of nearest-dates fares
    through a hub (Astana → Johannesburg, Johannesburg → Harare). A guide to the price, not a plan to fly: the
    days are matched when the tickets are bought."""
    found = guide_hubs(network, origin, destination)
    if not found:
        return None
    pairs = await asyncio.gather(
        *(asyncio.gather(flights.route(origin, h), flights.route(h, destination)) for h in found)
    )
    guides = [
        HubGuide(city(h), a.cheapest, b.cheapest) for h, (a, b) in zip(found, pairs, strict=True) if a and b
    ]
    return min(guides, key=lambda g: g.price, default=None)
