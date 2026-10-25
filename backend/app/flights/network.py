"""The route map: which cities have a direct flight between them, from the committed seed.

One node per city (airports folded in, see dictionary.city_code), one directed link per city pair with
the airlines that fly it. It says what exists, not what it costs: prices live in the fares table.
The seed is Travelpayouts' route list, which lags reality by months; a ticket we actually see beats it
(observe): a direct ticket confirms a link or adds a new one, and a route with tickets but none of them
direct makes a listed link that never showed a direct ticket «doubtful». Doubtful is weak evidence (we only see the cheapest tickets, and
routes are seasonal), so it ranks a link lower but never removes it.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from functools import cache
from typing import Literal

LinkStatus = Literal["listed", "seen", "doubtful"]

from app.flights.dictionary import SEED, City, cities, city, city_code, distance_km

CRUISE_KMH = 800  # block speed of a typical jet, gate to gate
TAXI_MIN = 30  # taxi, climb and descent on top of cruising


def estimate_minutes(km: float) -> int:
    """Flight time from distance, for a link we have no ticket for yet. Within ~15% on medium haul."""
    return round(km / CRUISE_KMH * 60 + TAXI_MIN)


@dataclass(frozen=True)
class Link:
    origin: City
    destination: City
    airlines: tuple[str, ...]
    km: int
    status: LinkStatus = "listed"  # listed: only the seed says so; seen: a direct ticket proved it

    @property
    def minutes(self) -> int:
        return estimate_minutes(self.km)

    def view(self) -> dict:
        return {
            "from": self.origin.code,
            "to": self.destination.code,
            "airlines": list(self.airlines),
            "km": self.km,
            "est_hours": round(self.minutes / 60 * 2) / 2,
            "status": self.status,
        }


@dataclass
class _Evidence:
    direct_at: datetime | None = None  # last time we saw a direct ticket
    indirect_at: datetime | None = None  # last time we saw tickets, none of them direct
    airlines: frozenset[str] = frozenset()


class Network:
    def __init__(self, routes: dict[str, dict[str, str]], known: dict[str, City]):
        self._cities = known
        self._out: dict[str, dict[str, tuple[str, ...]]] = {
            o: {d: tuple(airlines.split()) for d, airlines in ds.items() if d in known}
            for o, ds in routes.items()
            if o in known
        }
        self._evidence: dict[tuple[str, str], _Evidence] = {}

    def observe(self, origin: str, destination: str, direct_airline: str | None, at: datetime) -> None:
        """What a fetched fare says about the link: its direct ticket's airline, or None for «only transfers».
        Call it only when Aviasales had tickets: no tickets at all says nothing about the route."""
        o, d = city_code(origin), city_code(destination)
        if o not in self._cities or d not in self._cities or o == d:
            return
        seen = self._evidence.setdefault((o, d), _Evidence())
        if direct_airline is not None:
            if seen.direct_at is None or at >= seen.direct_at:
                seen.direct_at = at
            seen.airlines = seen.airlines | {direct_airline}
            self._out.setdefault(o, {}).setdefault(d, ())
        elif seen.indirect_at is None or at >= seen.indirect_at:
            seen.indirect_at = at

    def link(self, origin: str, destination: str) -> Link | None:
        o, d = city_code(origin), city_code(destination)
        airlines = self._out.get(o, {}).get(d)
        return None if airlines is None else self._make(o, d, airlines)

    def direct(self, origin: str, destination: str) -> bool:
        return self.link(origin, destination) is not None

    def links_from(self, origin: str) -> list[Link]:
        """Every direct flight out of a city, nearest first."""
        o = city_code(origin)
        found = [self._make(o, d, airlines) for d, airlines in self._out.get(o, {}).items()]
        return sorted(found, key=lambda link: link.km)

    def links_to(self, destination: str) -> list[Link]:
        d = city_code(destination)
        found = [self._make(o, d, ds[d]) for o, ds in self._out.items() if d in ds]
        return sorted(found, key=lambda link: link.km)

    def estimate(self, origin: str, destination: str) -> int | None:
        """Flight time for a direct flight between any two known cities, minutes; None for an unknown code."""
        a, b = city(origin), city(destination)
        return estimate_minutes(distance_km(a, b)) if a and b and a != b else None

    @property
    def size(self) -> tuple[int, int]:
        """(cities with a flight out, links)."""
        return len(self._out), sum(len(ds) for ds in self._out.values())

    def _make(self, o: str, d: str, airlines: tuple[str, ...]) -> Link:
        a, b = self._cities[o], self._cities[d]
        status: LinkStatus = "listed"
        seen = self._evidence.get((o, d))
        if seen:
            airlines = tuple(sorted(set(airlines) | seen.airlines))
            # a direct ticket is proof; missing from the cheapest tickets is only a hint
            status = "seen" if seen.direct_at else "doubtful"
        return Link(a, b, airlines, round(distance_km(a, b)), status)


@cache
def network() -> Network:
    routes = json.loads((SEED / "routes.json").read_text(encoding="utf-8"))
    return Network(routes, cities())
