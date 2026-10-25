"""Multi-city routes from the catalogue: which places chain well, how well they cover the user's interests,
how the nights split, and what every leg costs.

All of it runs in code, the model only picks and explains: a route the code did not build cannot be shown.
Legs between cities use real Aviasales tickets when there is a flight; short hops are an honest estimate
by distance (bus, train or car), marked as such.
"""

import asyncio
import math
from dataclasses import dataclass, field
from datetime import timedelta
from itertools import combinations, pairwise, permutations

from pydantic import Field

from app.catalog.catalog import KIDS_LABELS, KIND_LABELS, VISA_LABELS
from app.catalog.search import EASY_VISA, MONTHS, MONTHS_IN, SearchQuery, Snapshot, failures, in_scope
from app.flights import City, Flights, RouteFlights, Ticket
from app.flights.client import merged

MAX_LEG_KM = 1100  # further than this the hop is a separate trip, not a leg of one
FLIGHT_FROM_KM = 550  # shorter hops go by land even when there is an airport
GROUND_MAX_KM = 650  # a longer hop needs a plane: both ends must have an airport
GROUND_KMH = 60
ROAD_DETOUR = 1.3  # roads are longer than the straight line
MIN_NIGHTS_PER_STOP = 2
DEFAULT_NIGHTS = 7
PRICED_CANDIDATES = 6  # routes that get real tickets before the final pick
DATE_SLACK_DAYS = 1  # a leg may leave a day earlier or later than the nights say
# Misses that do not rule a stop out: flights are judged per leg, and only sea stops need a warm sea.
LEG_MISSES = {"flight", "direct", "ticket", "train"}


class RouteQuery(SearchQuery):
    """The search filters, applied to every stop, plus the shape of the route."""

    nights: int | None = Field(None, ge=2, le=60, description="Nights for the whole route.")
    max_stops: int = Field(3, ge=2, le=3, description="Most cities on one route.")
    limit: int = Field(3, ge=1, le=5)


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

    def view(self) -> dict:
        view = {
            "from": self.origin,
            "to": self.destination,
            "mode": self.mode,
            "km": self.km,
            "hours": self.hours,
        }
        if self.ticket and self.flights:
            view["ticket"] = {**self.ticket.view(), "direct_available": self.flights.direct is not None}
            view["hours"] = round(self.ticket.duration_min / 60 * 2) / 2 or self.hours
        elif self.mode == "ground":
            view["estimate"] = "по земле: автобус, поезд или авто, оценка по расстоянию"
        else:
            view["estimate"] = "билетов на этот месяц не нашлось"
        return view


@dataclass
class RoutePlan:
    stops: list[Snapshot]
    nights: list[int]
    score: float
    match: int  # 0-100, shown on the card
    interests: list[dict]
    legs: list[Leg] = field(default_factory=list)
    dates_chained: bool = False  # every flight leg leaves after the nights before it, as the plan says

    @property
    def id(self) -> str:
        return "+".join(s.place.id for s in self.stops)

    @property
    def name(self) -> str:
        return " → ".join(s.place.name for s in self.stops)

    @property
    def total_rub(self) -> int:
        return sum(leg.ticket.price for leg in self.legs if leg.ticket)

    @property
    def priced(self) -> bool:
        """Every flight leg has a real ticket, so the total is the whole cost of getting around."""
        return all(leg.ticket for leg in self.legs if leg.mode == "flight")


def km_between(a_lat: float, a_lon: float, b_lat: float, b_lon: float) -> int:
    lat1, lat2 = math.radians(a_lat), math.radians(b_lat)
    dlat, dlon = lat2 - lat1, math.radians(b_lon - a_lon)
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return round(6371 * 2 * math.asin(math.sqrt(h)))


def _km(a: Snapshot, b: Snapshot) -> int:
    return km_between(a.place.lat, a.place.lon, b.place.lat, b.place.lon)


def hop_hours(km: int, flying: bool) -> float:
    hours = 1.2 + km / 750 if flying else km * ROAD_DETOUR / GROUND_KMH
    return max(0.5, round(hours * 2) / 2)


def stop_fits(s: Snapshot, q: SearchQuery) -> bool:
    """A place can be a stop when it fails nothing but leg constraints; the sea filter binds sea stops only."""
    return all(
        m.kind in LEG_MISSES or (m.kind == "sea" and "sea" not in s.place.kinds) for m in failures(s, q)
    )


def _stop_scope(s: Snapshot, q: RouteQuery) -> bool:
    # a sea filter on a route means «a sea stop must be warm», not «every stop is a beach»
    loose = q.model_copy(update={"min_sea_temp": None})
    return in_scope(s, loose)


def _comfort(s: Snapshot, month: int | None) -> float:
    """1 for a pleasant dry day for walking around; lower when it is cold, very hot or rains a lot."""
    climate = s.climate.get(month, {}) if month else {}
    day = climate.get("air_max")
    if day is None:
        return 0.6
    gap = 0 if 18 <= day <= 30 else 18 - day if day < 18 else day - 30
    rain = climate.get("rain_days") or 0
    return max(0.0, 1 - gap / 15) * (1 - min(max(rain - 6, 0) / 20, 0.5))


def split_nights(total: int, stops: list[Snapshot]) -> list[int]:
    """Even split; the spare nights go to the stops with more to do (more kinds of trip)."""
    base, spare = divmod(total, len(stops))
    order = sorted(range(len(stops)), key=lambda i: -len(stops[i].place.kinds))
    nights = [base] * len(stops)
    for i in order[:spare]:
        nights[i] += 1
    return nights


def _interests(stops: list[Snapshot], wanted: list[str]) -> list[dict]:
    covered = {k for s in stops for k in s.place.kinds}
    shown = list(dict.fromkeys([*wanted, *sorted(covered)]))
    return [
        {"kind": k, "label": KIND_LABELS[k], "covered": k in covered, "wanted": k in wanted} for k in shown
    ]


def score_route(stops: list[Snapshot], q: RouteQuery) -> tuple[float, int]:
    """How well the route fits, and the same as a «совпадение» percentage for the card."""
    wanted = set(q.kinds or [])
    covered = {k for s in stops for k in s.place.kinds}
    interest = len(wanted & covered) / len(wanted) if wanted else min(len(covered), 3) / 3
    variety = min(len(covered), 3) / 3
    comfort = sum(_comfort(s, q.month) for s in stops) / len(stops)
    hops = sum(hop_hours(_km(a, b), _km(a, b) >= FLIGHT_FROM_KM) for a, b in pairwise(stops))
    ease = 1 - min(hops / 12, 1)
    visas = sum(s.visa_rule not in EASY_VISA for s in stops)
    match = 0.55 * interest + 0.15 * variety + 0.2 * comfort + 0.1 * ease - 0.1 * visas
    score = match - 0.04 * sum(s.place.price_level for s in stops) / len(stops)
    return score, max(0, min(100, round(match * 100)))


def plan_of(stops: list[Snapshot], q: RouteQuery) -> RoutePlan:
    """A route through these places in this order, scored and with the nights split."""
    score, match = score_route(stops, q)
    nights = split_nights(q.nights or DEFAULT_NIGHTS, stops)
    return RoutePlan(stops, nights, score, match, _interests(stops, q.kinds or []))


def _hop_ok(a: Snapshot, b: Snapshot, km: int) -> bool:
    """Close enough to go by land, or both ends have an airport and it is still one leg of a trip."""
    return km <= GROUND_MAX_KM or (km <= MAX_LEG_KM and bool(a.place.airport and b.place.airport))


def _order(
    group: tuple[int, ...], km: list[list[int]], start_km: list[int], stops: list[Snapshot]
) -> tuple[int, ...] | None:
    """The order to travel: every hop within reach, starting near home so there is no backtracking."""
    best = None
    for order in permutations(group):
        hops = [km[a][b] for a, b in pairwise(order)]
        if not all(_hop_ok(stops[a], stops[b], km[a][b]) for a, b in pairwise(order)):
            continue
        key = sum(hops) + start_km[order[0]] * 0.3
        if best is None or key < best[0]:
            best = (key, order)
    return best[1] if best else None


def candidate_routes(snapshots: list[Snapshot], q: RouteQuery, home: City | None) -> list[RoutePlan]:
    stops = [s for s in snapshots if _stop_scope(s, q) and stop_fits(s, q)]
    nights = q.nights or DEFAULT_NIGHTS
    most = min(q.max_stops, max(2, nights // MIN_NIGHTS_PER_STOP))
    sized = q.model_copy(update={"nights": nights})
    km = [[_km(a, b) for b in stops] for a in stops]
    start_km = [km_between(home.lat, home.lon, s.place.lat, s.place.lon) if home else 0 for s in stops]
    plans = []
    for size in range(2, most + 1):
        for group in combinations(range(len(stops)), size):
            # a group is worth ordering only when each place has a neighbour within reach
            if any(min(km[i][j] for j in group if j != i) > MAX_LEG_KM for i in group):
                continue
            order = _order(group, km, start_km, stops)
            if order is None:
                continue
            plans.append(plan_of([stops[i] for i in order], sized))
    return sorted(plans, key=lambda p: -p.score)


async def price_route(plan: RoutePlan, flights: Flights, origin: City | None, month: int | None) -> RoutePlan:
    """Real tickets for every leg: home to the first city, between cities, and back from the last one."""
    points = [(origin.name, origin.code, origin.lat, origin.lon)] if origin else []
    points += [(s.place.name, s.place.airport or "", s.place.lat, s.place.lon) for s in plan.stops]
    if origin:
        points.append(points[0])
    legs = []
    for (a_name, a_code, a_lat, a_lon), (b_name, b_code, b_lat, b_lon) in pairwise(points):
        km = km_between(a_lat, a_lon, b_lat, b_lon)
        flying = km >= FLIGHT_FROM_KM and bool(a_code and b_code)
        mode = "flight" if flying else "ground"
        legs.append(Leg(a_name, b_name, km, mode, hop_hours(km, flying), (a_code, b_code)))
    flown = [leg for leg in legs if leg.mode == "flight"]
    # later legs may leave next month (ten nights from 25 October is November), so they search both months
    following = None if month is None else month % 12 + 1
    found = await asyncio.gather(
        *(flights.route(*leg.codes, month) for leg in flown),
        *(flights.route(*leg.codes, following) for leg in flown[1:] if following),
    )
    later = iter(found[len(flown) :])
    for i, leg in enumerate(flown):
        leg.flights = merged(found[i], next(later)) if i and following else found[i]
    plan.legs = legs
    plan.dates_chained = chain_dates(legs, plan.nights, start_at_home=origin is not None)
    return plan


def chain_dates(legs: list[Leg], nights: list[int], start_at_home: bool = True) -> bool:
    """Pick one ticket per flight leg so the dates follow the plan: each leg leaves when the nights before it
    are over (give or take a day). The cheapest such chain wins. When no chain exists, every leg keeps its
    cheapest ticket and the route says its dates do not chain yet."""
    # days from the first departure to each leg: a leg leaves once the stops before it are over
    stays_before = [sum(nights[: j if start_at_home else j + 1]) for j in range(len(legs))]
    priced = [(j, leg) for j, leg in enumerate(legs) if leg.flights]
    if not priced:
        return False
    best: tuple[int, dict[int, Ticket]] | None = None
    first_j, first = priced[0]
    for anchor in first.flights.tickets or (first.flights.cheapest,):
        start = anchor.day - timedelta(days=stays_before[first_j])
        picks, total = {first_j: anchor}, anchor.price
        for j, leg in priced[1:]:
            target = start + timedelta(days=stays_before[j])
            fits = [t for t in leg.flights.tickets if abs((t.day - target).days) <= DATE_SLACK_DAYS]
            if not fits:
                break
            picks[j] = fits[0]  # tickets come cheapest first
            total += fits[0].price
        else:
            if best is None or total < best[0]:
                best = (total, picks)
    for j, leg in priced:
        leg.ticket = best[1][j] if best else leg.flights.cheapest
    return best is not None


async def find_routes(
    snapshots: list[Snapshot], q: RouteQuery, flights: Flights, origin: City | None
) -> list[RoutePlan]:
    """The best routes with real prices; at most one route per set of overlapping cities."""
    candidates = candidate_routes(snapshots, q, origin)[:PRICED_CANDIDATES]
    await asyncio.gather(*(price_route(plan, flights, origin, q.month) for plan in candidates))
    for plan in candidates:
        if not plan.legs or (plan.legs[0].mode == "flight" and not plan.legs[0].flights):
            plan.score -= 0.3  # no way to get there from home this month
    ranked = sorted(candidates, key=lambda p: -p.score)
    picked: list[RoutePlan] = []
    # first routes that share no city, so the choice is a real choice; then near ones if there are too few
    for most_shared in (0.0, 0.5):
        for plan in ranked:
            ids = {s.place.id for s in plan.stops}
            fresh = all(_overlap(ids, {s.place.id for s in o.stops}) <= most_shared for o in picked)
            if len(picked) < q.limit and plan not in picked and fresh:
                picked.append(plan)
    return picked


def _overlap(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b)


def _day(s: Snapshot, month: int | None) -> int | None:
    day = s.climate.get(month, {}).get("air_max") if month else None
    return None if day is None else round(day)


def route_for_model(plan: RoutePlan, month: int | None) -> dict:
    return {
        "id": plan.id,
        "name": plan.name,
        "match_percent": plan.match,
        "stops": [
            {
                "id": s.place.id,
                "name": s.place.name,
                "country": s.place.country.name,
                "nights": n,
                "kinds": [KIND_LABELS[k] for k in s.place.kinds],
                "day_c": _day(s, month),
                "visa": VISA_LABELS.get(s.visa_rule, s.visa_rule),
                "highlights": list(s.place.highlights[:2]),
            }
            for s, n in zip(plan.stops, plan.nights, strict=True)
        ],
        "legs": [leg.view() for leg in plan.legs],
        "tickets_total_rub": plan.total_rub or None,
        "all_flights_priced": plan.priced,
        "dates_chained": plan.dates_chained,
        "interests": {i["label"]: i["covered"] for i in plan.interests},
    }


def route_card(plan: RoutePlan, month: int | None, why: str, tradeoff: str | None) -> dict:
    """The route as the chat draws it: a wide banner made of its stops, the legs between them, the total."""
    stops = []
    for s, nights in zip(plan.stops, plan.nights, strict=True):
        climate = s.climate.get(month) if month else None
        stops.append(
            {
                "id": s.place.id,
                "name": s.place.name,
                "country": s.place.country.name,
                "country_code": s.place.country.code,
                "kinds": list(s.place.kinds),
                "nights": nights,
                "day": round(climate["air_max"]) if climate and "air_max" in climate else None,
                "sea": round(climate["sea_temp"]) if climate and "sea_temp" in climate else None,
                "visa": VISA_LABELS.get(s.visa_rule, s.visa_rule),
                "visa_easy": s.visa_rule in EASY_VISA,
                "highlights": list(s.place.highlights[:2]),
            }
        )
    kids = min((s.place.kids for s in plan.stops), key=["poor", "ok", "good"].index)
    return {
        "type": "route",
        "id": plan.id,
        "name": plan.name,
        "month_in": MONTHS_IN[month - 1] if month else None,
        "month": MONTHS[month - 1] if month else None,
        "stops": stops,
        "legs": [leg.view() for leg in plan.legs],
        "total_rub": plan.total_rub or None,
        "total_complete": plan.priced,
        "dates_chained": plan.dates_chained,
        "match": plan.match,
        "interests": plan.interests,
        "kids": KIDS_LABELS[kids],
        "why": why,
        "tradeoff": tradeoff,
    }
