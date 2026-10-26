"""A better way for a bad flight: Samarkand → Astana with two transfers and a high fare is rarely the answer.

For a flight leg with a transfer or no ticket at all, three kinds of alternatives are priced with real fares:
- change planes yourself in a hub that has direct flights both ways (Samarkand → Almaty → Astana);
- go by land to a neighbouring airport with a direct flight (train to Tashkent, then fly home);
- fly direct to a neighbouring airport and go on by land.
The route map (app.flights.network) picks the candidates before a single fare is asked for. Every way is
valued in roubles: its price plus time and transfers, weighted like the planner's «balanced». A way replaces
the direct flight only when it is clearly better; the leg keeps what the direct one was in `instead`.
"""

import asyncio
import math
from dataclasses import replace
from datetime import date, datetime, timedelta

from app.flights import City, Flights, RouteFlights, Ticket
from app.flights.client import merged
from app.flights.connections import connect, hubs
from app.flights.dictionary import city, distance_km, time_zone
from app.flights.network import Network
from app.ground import GroundOption, GroundRoute, transport
from app.ground.model import priced_first
from app.trip.legs import GROUND_MAX_KM, Leg, hop_hours, units

PER_HOUR = 1_500  # roubles an hour of travel is worth
PER_TRANSFER = 3_000
NO_TICKET_RUB = 100_000  # a way without a ticket counts as a very expensive one, never as a free one
NEAR_KM = 500  # a neighbouring airport, reached by train or bus
NEAR_PER_SIDE = 3
MIN_SAVING_RUB = 2_000
MIN_SAVING_SHARE = 0.15
AIRPORT_MIN = 120  # to the airport, check-in, security, bags: on top of the flight itself
HOPEFUL_KMH = 90  # a good train
HOPEFUL_RUB_PER_KM = 2.5
LAND_ONLY_KM = 1_500  # beyond this, a whole leg by land is a day and a night on a train
VERIFY = 3  # ways checked against real trains and buses, best on paper first
STATION_MIN = 90  # off the plane: bags, passport control, the road to the station
CHECK_IN_MIN = 180  # off the train and to the airport in time for the next plane
WAIT_PER_HOUR = 500  # an hour at a station, roubles: less than an hour on the move, but not free
DAY_MIN = 24 * 60


def value(cost: int | None, minutes: int, transfers: int) -> float:
    return (cost if cost is not None else NO_TICKET_RUB) + PER_HOUR * minutes / 60 + PER_TRANSFER * transfers


def _flights_in(leg: Leg) -> int:
    return sum(1 for p in (leg.parts or [leg]) if p.mode == "flight")


def leg_value(leg: Leg) -> float:
    """Price, time and transfers in roubles; a flight also costs the trip to the airport and the queues,
    which a train from the city centre does not, and a wait for the train after the plane counts too."""
    airports = AIRPORT_MIN * _flights_in(leg)
    waits = sum(p.ground.wait_min for p in units(leg) if p.ground)
    return value(leg.cost_rub, leg.minutes + airports + waits, leg.transfers)


def _hopeful_value(leg: Leg) -> float:
    """The value if every unchecked hop by land turns out a fast cheap train: a way that loses even then
    is not worth a timetable request."""
    cost, minutes = 0, AIRPORT_MIN * _flights_in(leg)
    for part in leg.parts or [leg]:
        if part.mode == "ground" and not part.ground:
            cost += round(part.km * HOPEFUL_RUB_PER_KM)
            minutes += round(part.km * 1.15 / HOPEFUL_KMH * 60)
        else:
            cost += part.cost_rub if part.cost_rub is not None else NO_TICKET_RUB
            minutes += part.minutes
    return value(cost, minutes, leg.transfers)


def wants_better(leg: Leg) -> bool:
    """A flight with no ticket or with a transfer: a direct flight is already as good as it gets."""
    return leg.mode == "flight" and not leg.parts and (leg.ticket is None or leg.ticket.transfers >= 1)


def _ticket_for(found: RouteFlights, day: date | None) -> Ticket:
    """The ticket for the leg's day (or the next); else the one closest to that day; without a day, the best
    by value: a cheap fare three weeks off is no answer for this leg."""
    calendar = found.by_day or (found.cheapest,)
    worth = lambda t: value(t.price, t.duration_min, t.transfers)
    if day:
        near = [t for t in calendar if t.day in (day, day + timedelta(days=1))]
        if near:
            return min(near, key=worth)
        dated = [t for t in calendar if t.day]
        if dated:
            return min(dated, key=lambda t: (abs((t.day - day).days), worth(t)))
    pool = {id(t): t for t in (*calendar, found.cheapest, found.direct, found.fastest) if t}
    return min(pool.values(), key=worth)


def _flight(a: City, b: City, found: RouteFlights, ticket: Ticket) -> Leg:
    km = round(distance_km(a, b))
    return Leg(
        a.name, b.name, km, "flight", hop_hours(km, True), (a.code, b.code), flights=found, ticket=ticket
    )


def _land(a: City, b: City) -> Leg:
    km = round(distance_km(a, b))
    return Leg(a.name, b.name, km, "ground", hop_hours(km, False), (a.code, b.code))


def _near(network: Network, a: City, b: City) -> tuple[list[City], list[City]]:
    """Airports next to A with a direct flight to B, and airports next to B with a direct flight from A."""
    before = [
        link.origin
        for link in network.links_to(b.code)
        if link.origin.code not in (a.code, b.code)
        and distance_km(a, link.origin) <= min(NEAR_KM, GROUND_MAX_KM)
    ]
    after = [
        link.destination
        for link in network.links_from(a.code)
        if link.destination.code not in (a.code, b.code)
        and distance_km(link.destination, b) <= min(NEAR_KM, GROUND_MAX_KM)
    ]
    by_a = sorted(before, key=lambda c: distance_km(a, c))[:NEAR_PER_SIDE]
    by_b = sorted(after, key=lambda c: distance_km(c, b))[:NEAR_PER_SIDE]
    return by_a, by_b


async def ways(
    a: City,
    b: City,
    month: int | None,
    day: date | None,
    flights: Flights,
    network: Network,
    also: int | None = None,
) -> list[list[Leg]]:
    """Every alternative with real fares, as lists of parts."""
    hub_cities = [h for code in hubs(network, a.code, b.code) if (h := city(code))]
    by_a, by_b = _near(network, a, b)
    asks = {
        *((a.code, h.code) for h in hub_cities),
        *((h.code, b.code) for h in hub_cities),
        *((h.code, b.code) for h in by_a),
        *((a.code, h.code) for h in by_b),
    }
    keys = sorted(asks)
    months = [month, also] if also else [month]  # a leg late in the trip may fly next month
    answers = await asyncio.gather(*(flights.route(o, d, m) for o, d in keys for m in months))
    fares = {key: merged(*answers[i * len(months) : (i + 1) * len(months)]) for i, key in enumerate(keys)}
    found: list[list[Leg]] = []
    for h in hub_cities:
        first, second = fares.get((a.code, h.code)), fares.get((h.code, b.code))
        if first and second and (c := connect(h, first, second, value, day)):
            found.append([_flight(a, h, first, c.first), _flight(h, b, second, c.second)])
    for h in by_a:  # by land first, then fly
        if fare := fares.get((h.code, b.code)):
            found.append([_land(a, h), _flight(h, b, fare, _ticket_for(fare, day))])
    for h in by_b:  # fly first, then by land
        if fare := fares.get((a.code, h.code)):
            found.append([_flight(a, h, fare, _ticket_for(fare, day)), _land(h, b)])
    if distance_km(a, b) <= LAND_ONLY_KM:  # no plane at all: a train or a bus the whole way
        found.append([_land(a, b)])
    return found


def _clear_win(current: float, score: float, had_ticket: bool) -> bool:
    if not had_ticket:  # no ticket at all: any way with tickets is better
        return score < current
    return current - score >= max(MIN_SAVING_RUB, MIN_SAVING_SHARE * current)


def _clock(text: str) -> int:
    hours, minutes = text[:5].split(":")
    return int(hours) * 60 + int(minutes)


def _wait(option: GroundOption, ready: datetime | None, deadline: datetime | None) -> float:
    """Minutes between the plane and the ride: after landing (`ready`) or before the next take-off
    (`deadline`). A timetable runs every day, so the train that left before the landing is tomorrow's; a ride
    on its date that does not fit is no ride at all."""
    if ready and option.departs:
        if option.dated:
            gap = (datetime.fromisoformat(option.departs) - ready).total_seconds() / 60
            return gap if gap >= 0 else math.inf
        return (_clock(option.departs) - (ready.hour * 60 + ready.minute)) % DAY_MIN
    if deadline and option.arrives:
        if option.dated:
            gap = (deadline - datetime.fromisoformat(option.arrives)).total_seconds() / 60
            return gap if gap >= 0 else math.inf
        return ((deadline.hour * 60 + deadline.minute) - _clock(option.arrives)) % DAY_MIN
    return 0


def _local(moment: datetime | None, place: City | None) -> datetime | None:
    zone = time_zone(place) if place else None
    return moment.astimezone(zone) if moment and zone else moment


def _timed(found: GroundRoute, part: Leg, before: Ticket | None, after: Ticket | None) -> GroundRoute:
    """The train or bus that fits the flights next to it, by the local clock of the station."""
    landed = before.arrives if before else None
    takeoff = after.departs if after else None
    if not landed and not takeoff:
        return found
    a, b = city(part.codes[0]), city(part.codes[1])
    ready = _local(landed + timedelta(minutes=STATION_MIN), a) if landed else None
    deadline = _local(takeoff - timedelta(minutes=CHECK_IN_MIN), b) if takeoff else None
    waits = {id(o): _wait(o, ready, deadline) for o in found.options}
    fits = [o for o in found.options if waits[id(o)] < math.inf]
    if not fits:
        return replace(found, picked=None, wait_min=0)
    worth = lambda o: (o.price_rub or 0) + 300 * o.minutes / 60 + WAIT_PER_HOUR * waits[id(o)] / 60
    pick = min(priced_first(fits), key=worth)
    return replace(found, picked=pick, wait_min=round(waits[id(pick)]))


def fit_rides(parts: list[Leg]) -> None:
    """Every train or bus of a smart way set to the flights around it: once more after the dates are chained,
    since that may move a flight to another time."""
    for i, part in enumerate(parts):
        if part.mode != "ground" or not part.ground:
            continue
        before = parts[i - 1].ticket if i else None
        after = parts[i + 1].ticket if i + 1 < len(parts) else None
        part.ground = _timed(part.ground, part, before, after)
        part.hours = round(part.ground.best.minutes / 60 * 2) / 2


async def _checked(parts: list[Leg], day: date | None) -> bool:
    """Looks up the real train or bus for every hop by land. A hop across a border with nothing found is
    not offered: a road that may need a visa run or a closed checkpoint is no estimate to rely on."""
    for part in parts:
        if part.mode != "ground":
            continue
        a, b = city(part.codes[0]), city(part.codes[1])
        found = await transport().route(a, b, day) if a and b else None
        if found:
            part.ground = found
            part.hours = round(found.best.minutes / 60 * 2) / 2
        elif not a or not b or a.country != b.country:
            return False
    fit_rides(parts)
    return True


async def better_way(
    leg: Leg,
    a: City,
    b: City,
    month: int | None,
    day: date | None,
    flights: Flights,
    network: Network,
    also: int | None = None,
) -> Leg | None:
    """The leg made of parts when a way beats the direct flight clearly, else None. Ways are checked from the
    best on paper; a way by land counts only once its train or bus is found (or it stays in one country),
    and one that could not win even with a fast cheap train is not looked up at all."""
    if not wants_better(leg) or a.code == b.code:
        return None
    current, had_ticket = leg_value(leg), leg.ticket is not None
    options = [
        replace(leg, parts=parts, ticket=None)
        for parts in await ways(a, b, month, day, flights, network, also)
    ]
    hopeful = sorted(
        (w for w in options if _clear_win(current, _hopeful_value(w), had_ticket)), key=_hopeful_value
    )
    best: tuple[float, Leg] | None = None
    for way in hopeful[:VERIFY]:
        if not await _checked(way.parts, day):
            continue
        way = replace(way, hours=round(sum(p.minutes for p in way.parts) / 60 * 2) / 2)
        score = leg_value(way)
        if _clear_win(current, score, had_ticket) and (best is None or score < best[0]):
            best = (score, way)
    if best is None:
        return None
    instead = None
    if leg.ticket:
        instead = {
            "price_rub": leg.ticket.price,
            "transfers": leg.ticket.transfers,
            "hours": round(leg.ticket.duration_min / 60 * 2) / 2,
            "airline": leg.ticket.view()["airline_name"],
        }
    return replace(best[1], instead=instead)
