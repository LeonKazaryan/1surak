"""Cheaper by changing planes yourself: A → hub → B on two separate tickets.

The route map picks the hubs before we pay for a single request: cities with a direct flight from A and a
direct flight on to B, that add little distance. Then the two calendars (cheapest ticket per day) are
matched so the second flight leaves 3 to 30 hours after the first lands: two prices from different days
of the month would be a plan nobody can fly.
"""

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
