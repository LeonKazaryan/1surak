"""One leg of a route: a flight with a real ticket, a hop by land, or a smarter way made of parts.

A leg always goes from one point of the route to the next (home → first city → … → home), so whoever lays
the legs next to the stops (the cards, the trip plan) can keep counting legs. When a direct flight is bad, the
leg keeps its two ends and gets `parts`: train to Tashkent, then a direct flight home. `instead` remembers
what the direct way would have cost, for the card to show the saving.
"""

import math
import statistics
from dataclasses import dataclass, field, replace
from datetime import date

from app.flights import RouteFlights, Ticket
from app.flights.client import search_on
from app.ground import GroundRoute

FLIGHT_FROM_KM = 400  # shorter hops go by land even when there is an airport (Antalya → Alanya)
GROUND_MAX_KM = 650  # a longer hop needs a plane: both ends must have an airport
GROUND_KMH = 60
ROAD_DETOUR = 1.3  # roads are longer than the straight line
GROUND_RUB_PER_KM = 5  # a bus or train seat, per person: an estimate, never a quote
USUAL_FROM_DAYS = 4  # days with a fare that month before there is a usual price to compare with
PRICEY_SHARE = 1.3  # a ticket this much above the month's usual price is marked as dear
PRICEY_RUB = 3_000  # and at least this much: 30% of a short hop is small change


def km_between(a_lat: float, a_lon: float, b_lat: float, b_lon: float) -> int:
    lat1, lat2 = math.radians(a_lat), math.radians(b_lat)
    dlat, dlon = lat2 - lat1, math.radians(b_lon - a_lon)
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return round(6371 * 2 * math.asin(math.sqrt(h)))


def hop_hours(km: int, flying: bool) -> float:
    hours = 1.2 + km / 750 if flying else km * ROAD_DETOUR / GROUND_KMH
    return max(0.5, round(hours * 2) / 2)


def ground_estimate_rub(km: int) -> int:
    return round(km * ROAD_DETOUR * GROUND_RUB_PER_KM / 100) * 100


@dataclass
class Leg:
    origin: str
    destination: str
    km: int
    mode: str  # flight | ground
    hours: float
    codes: tuple[str, str] = ("", "")  # IATA of both ends, for the ticket search
    flights: RouteFlights | None = None
    ticket: Ticket | None = None  # the one picked so the dates of the whole route chain
    ground: GroundRoute | None = None  # real trains or buses for a hop by land
    parts: list["Leg"] = field(default_factory=list)  # a smarter way than the direct flight
    instead: dict | None = None  # the direct way it replaced: price, transfers, hours
    from_stop: int | None = None  # index of the route's city it leaves, None for home
    to_stop: int | None = None  # index of the city it arrives at, None for home
    # No fare cached for the month: the route on its nearest dates, and the ticket from them that stands in
    # for the price (a guide, not a ticket for the trip's day), with the live search for that day.
    nearby: RouteFlights | None = None
    guide: Ticket | None = None
    day: date | None = None  # the day the plan has this leg on, for the live search

    @property
    def usual_rub(self) -> int | None:
        """The route's usual fare that month: the median of the cheapest ticket of each day."""
        days = self.flights.by_day if self.flights else ()
        return round(statistics.median(t.price for t in days)) if len(days) >= USUAL_FROM_DAYS else None

    @property
    def pricey(self) -> bool:
        """The ticket on the plan's dates costs clearly more than the route usually does that month."""
        usual = self.usual_rub
        return bool(
            self.ticket
            and usual
            and self.ticket.price >= usual * PRICEY_SHARE
            and self.ticket.price - usual >= PRICEY_RUB
        )

    @property
    def search_link(self) -> str | None:
        return search_on(*self.codes, self.day) if self.day and all(self.codes) else None

    @property
    def via(self) -> str | None:
        """The city a smart way changes in: «Ташкент»."""
        return self.parts[0].destination if self.parts else None

    @property
    def ground_rub(self) -> int | None:
        """A ground hop's fare: the real one when a train or bus was found, else None (only an estimate)."""
        return self.ground.best.price_rub if self.ground else None

    @property
    def price_rub(self) -> int | None:
        """What the leg costs per person: its ticket, or the sum of its parts; None when part of it is unknown."""
        if self.parts:
            prices = [p.price_rub for p in self.parts]
            return None if any(p is None for p in prices) else sum(prices)
        if self.mode == "flight":
            return self.ticket.price if self.ticket else None
        return self.ground_rub

    @property
    def cost_rub(self) -> int | None:
        """For comparing ways: real prices where known, the distance estimate for a hop by land."""
        if self.parts:
            costs = [p.cost_rub for p in self.parts]
            return None if any(c is None for c in costs) else sum(costs)
        if self.mode == "flight":
            return self.ticket.price if self.ticket else None
        return self.ground_rub if self.ground_rub is not None else ground_estimate_rub(self.km)

    @property
    def minutes(self) -> int:
        if self.parts:
            return sum(p.minutes for p in self.parts)
        if self.ticket:
            return self.ticket.duration_min
        if self.ground:
            return self.ground.best.minutes
        return round(self.hours * 60)

    @property
    def transfers(self) -> int:
        if self.parts:
            return len(self.parts) - 1 + sum(p.transfers for p in self.parts)
        return self.ticket.transfers if self.ticket else 0

    def view(self) -> dict:
        view = {
            "from": self.origin,
            "to": self.destination,
            "mode": self.mode,
            "km": self.km,
            "hours": self.hours,
            "from_stop": self.from_stop,
            "to_stop": self.to_stop,
        }
        if self.parts:
            view["parts"] = [p.view() for p in self.parts]
            view["via"] = self.via
            view["hours"] = round(self.minutes / 60 * 2) / 2
            view["price_rub"] = self.price_rub
            if self.instead:
                view["instead"] = self.instead
            return view
        if self.ticket and self.flights:
            view["ticket"] = {**self.ticket.view(), "direct_available": self.flights.direct is not None}
            view["hours"] = round(self.ticket.duration_min / 60 * 2) / 2 or self.hours
            if self.pricey:
                view["usual_rub"] = self.usual_rub
            if self.day and self.ticket.day != self.day:  # the nearest ticket, on another day than the plan's
                view["date"] = self.day.isoformat()
                view["search_link"] = self.search_link
        elif self.ground:
            view["ground"] = self.ground.view()
            view["hours"] = view["ground"]["hours"]
        elif self.mode == "ground":
            view["estimate"] = "по земле: автобус, поезд или авто, оценка по расстоянию"
            view["estimate_rub"] = ground_estimate_rub(self.km)
        else:
            # never a dead end: the best ticket of the nearest dates as the price, the live search for the day
            if self.guide:
                view["guide"] = self.guide.view()
                view["hours"] = round(self.guide.duration_min / 60 * 2) / 2 or self.hours
            if self.day:
                view["date"] = self.day.isoformat()
            view["search_link"] = self.search_link
        return view


def units(leg: Leg) -> list[Leg]:
    """The flights and hops a leg is really made of: its parts, or the leg itself."""
    return leg.parts or [leg]


def leaving(leg: Leg) -> Leg:
    """The leg as seen from the city it leaves: a smart way starts with its first part."""
    if not leg.parts:
        return leg
    first = leg.parts[0]
    return replace(leg, mode=first.mode, ticket=first.ticket, hours=first.hours, km=first.km, parts=[])


def arriving(leg: Leg) -> Leg:
    """The leg as seen from the city it reaches: a flight part lands there, a train or bus after one arrives
    the whole way later."""
    if not leg.parts:
        return leg
    last = leg.parts[-1]
    if last.mode == "flight":
        return replace(leg, mode="flight", ticket=last.ticket, parts=[])
    return replace(leg, mode="ground", ticket=None, parts=[])
