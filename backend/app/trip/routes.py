"""Multi-city routes from the catalogue: which places chain well, how well they cover the user's interests,
how the nights split, and what every leg costs.

All of it runs in code, the model only picks and explains: a route the code did not build cannot be shown.
Legs between cities use real Aviasales tickets when there is a flight; a bad flight (transfers, no ticket)
gets a smarter way through a hub or a neighbouring airport (app.trip.smart); hops by land use real trains
and buses where an open timetable has them (app.ground), else an honest estimate by distance.
"""

import asyncio
import logging
import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from itertools import pairwise, permutations

from pydantic import Field

from app.catalog.catalog import KIDS_LABELS, KIND_LABELS, VISA_LABELS
from app.catalog.search import (
    EASY_VISA,
    MONTHS,
    MONTHS_IN,
    SearchQuery,
    Snapshot,
    failures,
    in_scope,
    route_visas,
    visa_info,
    visa_text,
)
from app.flights import City, Flights, Ticket
from app.flights.client import merged
from app.flights.connections import through_hub
from app.flights.dictionary import city, fame, reach
from app.flights.network import network
from app.ground import transport
from app.money import money
from app.photos import place_photo
from app.trip.brief import TripBrief
from app.trip.legs import (  # re-exported: the trip plan imports them from here
    FLIGHT_FROM_KM,
    GROUND_MAX_KM,
    ROAD_DETOUR,
    Leg,
    hop_hours,
    km_between,
    units,
)
from app.trip.smart import better_way, fit_rides, leg_value, value, wants_better
from app.visas import label as visa_label

log = logging.getLogger(__name__)

__all__ = ["ROAD_DETOUR", "Leg", "RoutePlan", "RouteQuery", "km_between"]

MAX_LEG_KM = 1100  # further than this the hop is a separate trip, not a leg of one
# through several countries a direct flight of about three and a half hours is still one leg: Cairo → Tunis
MAX_ACROSS_KM = 2600
FAMOUS_LINKS = 200  # Wikipedias with an article on a city as well known as it gets for a route (Cairo 261)
POPULAR_ROUTES = 100  # without that, direct routes of a city as well known as it gets (Cairo 86, Tunis 58)
POPULAR_WEIGHT = 0.15  # Cairo before Asyut, Marrakech before Nador
COUNTRIES_WEIGHT = 0.15  # several countries asked for: a route through fewer of them fits that much less
# a route with fewer cities than its nights hold ranks a little lower: 10 nights → 4 cities
STOPS_WEIGHT = 0.06
# the ends of a route are where the flights from and to home go: a small airport there costs this much more
# travel than a big one, so Cairo → … → Rabat → Casablanca flies home from Casablanca, not from Rabat
SMALL_END_KM = 500
BORDER_LAND_KM = (
    350  # across a border, a longer hop by land (a mountain pass, a closed crossing) needs a plane
)
# When the user wants trains: a hop goes by land this far (a night train at home, Moscow – Minsk across a
# border), and a long one keeps its plane only when no train or bus is found.
TRAIN_KM = 1_500
TRAIN_BORDER_KM = 1_000
MIN_NIGHTS_PER_STOP = 2
MAX_STOPS = 7
DEFAULT_NIGHTS = 7
PRICED_CANDIDATES = 6  # routes that get real tickets before the final pick
BEAM = 40  # partial routes kept at every length while growing them city by city
DATE_SLACK_DAYS = (1, 2)  # a leg may leave a day (then two) earlier or later than the nights say
MIN_LAYOVER = timedelta(hours=3)  # changing planes on separate tickets
MAX_LAYOVER = timedelta(hours=30)
GROUND_WAIT_S = 15.0  # trains and buses for a route, all together: past this the hops stay estimates
IMPROVE_WAIT_S = 25.0  # smarter ways for a route's bad flights, timetables included
DAY_OFF_RUB = 2_000  # with no chain, a ticket a day off the plan counts this much dearer
UNCHAINED_RUB = 5_000  # of two orders of the same cities, one whose dates do not chain counts dearer
START_DAY = 10  # with a month and no tickets, the land hops are looked up from the 10th
# Misses that do not rule a stop out: flights are judged per leg, and only sea stops need a warm sea.
LEG_MISSES = {"flight", "direct", "ticket", "train"}


def default_stops(nights: int) -> int:
    """Most cities for this many nights when the user did not say: 7 nights → 3, 10 → 4, 14 → 5, 18 → 7."""
    return max(2, min(MAX_STOPS, nights // 3 + 1))


class RouteQuery(SearchQuery):
    """The search filters, applied to every stop, plus the shape of the route."""

    nights: int | None = Field(None, ge=2, le=60, description="Nights for the whole route.")
    min_stops: int = Field(2, ge=2, le=MAX_STOPS, description="Fewest cities: 4-5 for «большой тур по …».")
    max_stops: int | None = Field(
        None,
        ge=2,
        le=MAX_STOPS,
        description="Most cities; by default it follows the nights (2 nights a city).",
    )
    limit: int = Field(3, ge=1, le=5)
    places: list[str] | None = Field(
        None,
        min_length=2,
        max_length=MAX_STOPS,
        description="The cities the user named, catalogue ids (route_places from the hint): the route goes "
        "through exactly these, the filters are not applied. Also for a theme the filters cannot see "
        "(Christmas markets, wine, carnivals): the 3-5 best-known cities for it, in different countries when "
        "the user wants several; names are fine ('Вена', 'Прага').",
    )
    order_fixed: bool = Field(False, description="With places: keep the user's order of the cities.")
    min_countries: int = Field(
        1,
        ge=1,
        le=MAX_STOPS,
        description="Fewest countries the route crosses: min_countries from the hint when the user wants "
        "several countries («несколько стран»).",
    )
    visas_matter: bool = Field(
        True,
        description="False when the user said the visa does not matter: no route is marked down for one.",
    )
    by_land: bool = Field(
        False,
        description="The user wants trains or buses, not planes («на поезде», «без самолётов»): every hop "
        "where a train or bus runs goes by land, home included; a plane only where none is found.",
    )

    @property
    def land(self) -> bool:
        """Trains wanted: by_land, or without_flight as the destination search names it."""
        return self.by_land or self.without_flight

    @property
    def max_leg_km(self) -> int:
        return MAX_ACROSS_KM if self.min_countries > 1 else MAX_LEG_KM


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
        """Tickets for the whole route, per person: flights and the trains or buses with a real fare."""
        return sum(p.price_rub or 0 for leg in self.legs for p in units(leg))  # a part's estimate is no fare

    @property
    def guide_rub(self) -> int:
        """The flights without a ticket, at the best fare of their nearest dates: a guide to the price."""
        return sum(leg.guide.price for leg in self.legs if leg.guide and not leg.ticket)

    @property
    def priced(self) -> bool:
        """Every flight, including the parts of a smart way, has a real ticket."""
        flown = [p for leg in self.legs for p in (leg.parts or [leg]) if p.mode == "flight"]
        return all(p.ticket for p in flown)


def _km(a: Snapshot, b: Snapshot) -> int:
    return km_between(a.place.lat, a.place.lon, b.place.lat, b.place.lon)


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
    """How well the route fits, and the same as a «совпадение» percentage for the card.
    Moving is judged per hop, so a long tour is not marked down for having more cities."""
    wanted = set(q.kinds or [])
    covered = {k for s in stops for k in s.place.kinds}
    interest = len(wanted & covered) / len(wanted) if wanted else min(len(covered), 3) / 3
    variety = min(len(covered), 3) / 3
    comfort = sum(_comfort(s, q.month) for s in stops) / len(stops)
    hops = [hop_hours(_km(a, b), _km(a, b) >= FLIGHT_FROM_KM) for a, b in pairwise(stops)]
    ease = 1 - min(sum(hops) / len(hops) / 8, 1)
    # the share of stops with a visa to get, not their count: five Schengen cities are one visa, not five
    visas = sum(s.visa_rule not in EASY_VISA for s in stops) / len(stops) if q.visas_matter else 0
    match = 0.55 * interest + 0.15 * variety + 0.2 * comfort + 0.1 * ease - 0.1 * visas
    if q.min_countries > 1:
        crossed = min(_countries(stops), q.min_countries) - 1
        match -= COUNTRIES_WEIGHT * (1 - crossed / (q.min_countries - 1))
    known = sum(popularity(s) for s in stops) / len(stops)
    target = min(q.max_stops or MAX_STOPS, default_stops(q.nights or DEFAULT_NIGHTS))
    filled = min(len(stops), target) / target
    score = (
        match
        - 0.04 * sum(s.place.price_level for s in stops) / len(stops)
        + POPULAR_WEIGHT * (known - 1)
        + STOPS_WEIGHT * (filled - 1)
    )
    return score, max(0, min(100, round(match * 100)))


def popularity(s: Snapshot) -> float:
    """How well known a place is, 0 to 1: the team's own places are; a city from the route map by the
    Wikipedias that write about it (Marrakech 0.84, Nador 0.51), else by how many cities fly to it directly."""
    if s.place.verified:
        return 1.0
    links = fame(s.place.airport) if s.place.airport else None
    return min(1.0, math.sqrt(links / FAMOUS_LINKS)) if links is not None else connected(s)


def connected(s: Snapshot) -> float:
    """How many cities fly to the place directly, 0 to 1: none without an airport."""
    routes = reach(s.place.airport) if s.place.airport else 0
    return min(1.0, math.log1p(routes) / math.log1p(POPULAR_ROUTES))


def _countries(stops: list[Snapshot]) -> int:
    return len({s.place.country.code for s in stops})


def plan_of(stops: list[Snapshot], q: RouteQuery) -> RoutePlan:
    """A route through these places in this order, scored and with the nights split."""
    score, match = score_route(stops, q)
    nights = split_nights(q.nights or DEFAULT_NIGHTS, stops)
    return RoutePlan(stops, nights, score, match, _interests(stops, q.kinds or []))


def _by_land(a_country: str, b_country: str, km: int) -> bool:
    """Whether a hop can go by land: up to GROUND_MAX_KM at home, BORDER_LAND_KM across a border."""
    return km <= (GROUND_MAX_KM if a_country == b_country else BORDER_LAND_KM)


def _by_train(a_country: str, b_country: str, km: int) -> bool:
    """Whether a hop may go by land for someone who wants trains: a night train's distance."""
    return km <= (TRAIN_KM if a_country == b_country else TRAIN_BORDER_KM)


def _hop_ok(a: Snapshot, b: Snapshot, km: int, land: bool = False, max_km: int = MAX_LEG_KM) -> bool:
    """Close enough to go by land, or a direct flight on the route map between them, still one leg of a trip.
    The map is what keeps Yerevan → Baku out: both have airports, but nothing flies between them."""
    countries = a.place.country.name, b.place.country.name
    if _by_land(*countries, km) or (land and _by_train(*countries, km)):
        return True
    if km > max_km or not (a.place.airport and b.place.airport):
        return False
    return network().direct(a.place.airport, b.place.airport)


def candidate_routes(snapshots: list[Snapshot], q: RouteQuery, home: City | None) -> list[RoutePlan]:
    """Routes grown city by city (a beam search): from every place, the next one within reach, keeping the
    best orders at each length. Up to seven cities without trying every combination of fifty places."""
    stops = [s for s in snapshots if _stop_scope(s, q) and stop_fits(s, q)]
    nights = q.nights or DEFAULT_NIGHTS
    most = min(q.max_stops or default_stops(nights), max(2, nights // MIN_NIGHTS_PER_STOP), len(stops))
    least = min(max(q.min_stops, q.min_countries), most)
    sized = q.model_copy(update={"nights": nights})
    km = [[_km(a, b) for b in stops] for a in stops]
    reach = [
        [i != j and _hop_ok(stops[i], stops[j], km[i][j], q.land, q.max_leg_km) for j in range(len(stops))]
        for i in range(len(stops))
    ]
    start_km = [km_between(home.lat, home.lon, s.place.lat, s.place.lon) if home else 0 for s in stops]
    small_end = [SMALL_END_KM * (1 - connected(s)) if home else 0 for s in stops]

    def travel(path: tuple[int, ...]) -> float:
        # out from home and back from the last city count less than the hops: a loop beats a zigzag
        # ties go to starting nearer home: the first flight is the one people check first
        ends = 0.31 * start_km[path[0]] + 0.29 * start_km[path[-1]] + small_end[path[0]] + small_end[path[-1]]
        return ends + sum(km[a][b] for a, b in pairwise(path))

    beam: list[tuple[int, ...]] = [(i,) for i in range(len(stops))]
    plans: list[RoutePlan] = []
    for size in range(2, most + 1):
        best: dict[frozenset[int], tuple[float, tuple[int, ...], RoutePlan]] = {}
        for path in beam:
            for j in range(len(stops)):
                if j in path or not reach[path[-1]][j]:
                    continue
                grown = (*path, j)
                plan = plan_of([stops[i] for i in grown], sized)
                rank = plan.score - travel(grown) / 20_000
                key = frozenset(grown)
                if key not in best or rank > best[key][0]:
                    best[key] = (rank, grown, plan)
        ranked = sorted(best.values(), key=lambda r: -r[0])
        if q.min_countries > 1:
            ranked = _mixes_first(ranked, stops)
        ranked = ranked[:BEAM]
        beam = [path for _, path, _ in ranked]
        if size >= least:
            # grown one city at a time, a path can zigzag: the shortest order of the same cities replaces it
            plans.extend(
                plan_of([stops[i] for i in _shortest(path, travel, reach)], sized) for _, path, _ in ranked
            )
    if q.min_countries > 1 and plans:
        # through as many of the countries as asked, or as many as can be reached
        wanted = min(q.min_countries, max(_countries(p.stops) for p in plans))
        plans = [p for p in plans if _countries(p.stops) >= wanted]
    return sorted(plans, key=lambda p: -p.score)


def _mixes_first(ranked: list, stops: list[Snapshot]) -> list:
    """The best path of every mix of countries first, then the rest by rank: a far country is not crowded out
    of the beam by a cluster of near cities in another."""
    seen: set[frozenset[str]] = set()
    first, rest = [], []
    for item in ranked:
        mix = frozenset(stops[i].place.country.code for i in item[1])
        (rest if mix in seen else first).append(item)
        seen.add(mix)
    return first + rest


def _shortest(path: tuple[int, ...], travel, reach: list[list[bool]]) -> tuple[int, ...]:
    """The order of these cities with the least travel, every hop within reach (7 cities: 5040 orders)."""
    best = path
    for order in permutations(path):
        if all(reach[a][b] for a, b in pairwise(order)) and travel(order) < travel(best):
            best = order
    return best


def _stop_city(s: Snapshot) -> City:
    """The stop as a city of the dictionary (its airport's city), or a point of its own for Anapa or Suzdal."""
    found = city(s.place.airport) if s.place.airport else None
    if found:
        return found
    name = s.place.name.split("(")[-1].rstrip(")").strip() if "(" in s.place.name else s.place.name
    return City(s.place.airport or "", name, s.place.country.name, s.place.lat, s.place.lon)


def _route_points(plan: RoutePlan, origin: City | None) -> list[tuple[City, str, int | None]]:
    """(city, the name to show, index of the stop or None for home) along the route."""
    points: list[tuple[City, str, int | None]] = [(origin, origin.name, None)] if origin else []
    points += [(_stop_city(s), s.place.name, i) for i, s in enumerate(plan.stops)]
    if origin:
        points.append((origin, origin.name, None))
    return points


def _stays_before(legs: list[Leg], nights: list[int], start_at_home: bool) -> list[int]:
    """Days from the first departure to each leg: a leg leaves once the stops before it are over."""
    return [sum(nights[: j if start_at_home else j + 1]) for j in range(len(legs))]


async def price_route(
    plan: RoutePlan,
    flights: Flights,
    origin: City | None,
    month: int | None,
    start: date | None = None,
    improve: bool = True,
    by_land: bool = False,
) -> RoutePlan:
    """Real tickets for every leg: home to the first city, between cities, and back from the last one.
    With `improve`, a bad flight gets a smarter way, and hops by land get real trains or buses. With
    `by_land` (the user wants trains) every hop within a night train's reach goes by land, and the trains are
    looked up first: a long hop with none found takes a plane after all."""
    points = _route_points(plan, origin)
    legs = []
    for (a, a_name, a_stop), (b, b_name, b_stop) in pairwise(points):
        km = km_between(a.lat, a.lon, b.lat, b.lon)
        if by_land:
            flying = bool(a.code and b.code) and not _by_train(a.country, b.country, km)
        else:
            flying = bool(a.code and b.code) and (
                km >= FLIGHT_FROM_KM or not _by_land(a.country, b.country, km)
            )
        mode = "flight" if flying else "ground"
        leg = Leg(
            a_name,
            b_name,
            km,
            mode,
            hop_hours(km, flying),
            (a.code, b.code),
            from_stop=a_stop,
            to_stop=b_stop,
        )
        legs.append(leg)
    plan.legs = legs
    home = origin is not None
    if by_land and improve:
        await _add_ground(plan, points, month, home)
        for leg, (a, *_), (b, *_) in zip(legs, points, points[1:], strict=False):
            if (
                leg.mode == "ground"
                and not leg.ground
                and a.code
                and b.code
                and not _by_land(a.country, b.country, leg.km)
            ):
                leg.mode, leg.hours = (
                    "flight",
                    hop_hours(leg.km, True),
                )  # no train on a long hop: a plane after all
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
    # no fare cached for the month is no dead end: the route's nearest dates give the price to plan with
    lacking = [leg for leg in flown if not leg.flights] if month is not None else []
    for leg, near in zip(
        lacking, await asyncio.gather(*(flights.route(*leg.codes) for leg in lacking)), strict=True
    ):
        leg.nearby = near
    # nobody has a fare for the route on any day (Astana → Harare): two tickets through a hub price it
    alone = [leg for leg in flown if not leg.flights and not leg.nearby]
    routes = network()
    for leg, via in zip(
        alone, await asyncio.gather(*(through_hub(*leg.codes, flights, routes) for leg in alone)), strict=True
    ):
        if via:
            leg.nearby, leg.guide_via = via.flights, via.where
    plan.dates_chained = chain_dates(legs, plan.nights, start_at_home=home, start=start)
    if improve:
        await _improve(plan, points, flights, month)
        plan.dates_chained = chain_dates(plan.legs, plan.nights, start_at_home=home, start=start)
        for leg in plan.legs:
            fit_rides(leg.parts)
        await _add_ground(plan, points, month, home)
    _add_guides(plan, month, home, start)
    return plan


def _add_guides(plan: RoutePlan, month: int | None, home: bool, start: date | None) -> None:
    """Every flight still without a ticket gets the best ticket of its nearest dates as its price, and the
    day the plan has it on, for the live search on Aviasales."""
    for leg, day in zip(plan.legs, _leg_days(plan, month, home, start), strict=True):
        if leg.mode != "flight" or leg.parts or leg.ticket:
            continue
        if leg.nearby:
            near = leg.nearby
            pool = {id(t): t for t in (*near.by_day, near.cheapest, near.direct, near.fastest) if t}
            leg.guide = min(pool.values(), key=lambda t: value(t.price, t.duration_min, t.transfers))
        leg.day = day or (leg.guide.day if leg.guide else None)


async def _improve(plan: RoutePlan, points: list, flights: Flights, month: int | None) -> None:
    """Smarter ways for the bad flights of the route, all priced at once."""
    bad = [j for j, leg in enumerate(plan.legs) if wants_better(leg)]
    if not bad:
        return
    routes = network()
    following = None if month is None else month % 12 + 1
    better = await _within(
        IMPROVE_WAIT_S,
        asyncio.gather(
            *(
                better_way(
                    plan.legs[j],
                    points[j][0],
                    points[j + 1][0],
                    month,
                    plan.legs[j].ticket.day if plan.legs[j].ticket else None,
                    flights,
                    routes,
                    following if j else None,
                )
                for j in bad
            )
        ),
    )
    if better is None:
        log.warning("Smarter ways took too long; the route keeps its direct flights")
        return
    for j, way in zip(bad, better, strict=True):
        if way:
            plan.legs[j] = way


async def _within(seconds: float, work):
    """The result of `work`, or None when it takes longer: a chat answer must not wait on a slow timetable."""
    try:
        return await asyncio.wait_for(work, seconds)
    except TimeoutError:
        return None


def _leg_days(plan: RoutePlan, month: int | None, home: bool, start: date | None = None) -> list[date | None]:
    """The day each leg is travelled: from the chained tickets, else the trip's start, else the 10th of
    the month."""
    stays = _stays_before(plan.legs, plan.nights, home)
    first = next(
        ((j, t) for j, leg in enumerate(plan.legs) for t in [_first_ticket(leg)] if t and t.day), None
    )
    if first:
        start = first[1].day - timedelta(days=stays[first[0]])
    elif start is None and month:
        today = date.today()
        start = date(today.year + (month < today.month), month, START_DAY)
    if start is None:
        return [None] * len(plan.legs)
    return [start + timedelta(days=s) for s in stays]


def _first_ticket(leg: Leg) -> Ticket | None:
    return next((p.ticket for p in (leg.parts or [leg]) if p.ticket), None)


async def _add_ground(plan: RoutePlan, points: list, month: int | None, home: bool) -> None:
    """Real trains and buses for every hop by land, the parts of smart ways included."""
    days = _leg_days(plan, month, home)
    hops: list[tuple[Leg, City, City, date | None]] = []
    for j, leg in enumerate(plan.legs):
        if leg.parts:  # a smart way's hops by land were looked up when it was picked
            ends = [
                (p, city(p.codes[0]), city(p.codes[1]))
                for p in leg.parts
                if p.mode == "ground" and not p.ground
            ]
            hops += [(p, a, b, days[j]) for p, a, b in ends if a and b]
        elif leg.mode == "ground" and not leg.ground:
            hops.append((leg, points[j][0], points[j + 1][0], days[j]))
    if not hops:
        return
    ground = transport()
    try:
        found = await asyncio.wait_for(
            asyncio.gather(*(ground.route(a, b, day) for _, a, b, day in hops)), GROUND_WAIT_S
        )
    except TimeoutError:
        log.warning("Trains and buses took too long; the hops stay estimates")
        return
    for (leg, *_), route in zip(hops, found, strict=True):
        if route:
            leg.ground = route
            leg.hours = round(route.best.minutes / 60 * 2) / 2


def _flight_items(legs: list[Leg], nights: list[int], start_at_home: bool) -> list[tuple[int, Leg, str]]:
    """Every flight with fares in travel order: (days from the first departure, the flight, how it follows).
    «own»: a leg of its own; «after_flight»: the second plane of a connection; «after_land»: a flight after a
    train or bus in the same smart way."""
    stays = _stays_before(legs, nights, start_at_home)
    items = []
    for j, leg in enumerate(legs):
        if leg.parts:
            for k, part in enumerate(leg.parts):
                if part.mode != "flight" or not part.flights:
                    continue
                before = leg.parts[k - 1] if k else None
                how = "own" if before is None else "after_flight" if before.mode == "flight" else "after_land"
                items.append((stays[j], part, how))
        elif leg.mode == "flight" and leg.flights:
            items.append((stays[j], leg, "own"))
    return items


def _layover_ok(before: Ticket, after: Ticket) -> bool:
    if before.arrives and after.departs:
        return MIN_LAYOVER <= after.departs - before.arrives <= MAX_LAYOVER
    return bool(before.day and after.day) and 0 <= (after.day - before.day).days <= 1


def chain_dates(
    legs: list[Leg], nights: list[int], start_at_home: bool = True, start: date | None = None
) -> bool:
    """Pick one ticket per flight so the dates follow the plan: each leg leaves when the nights before it
    are over (give or take a day), and the second plane of a connection leaves 3-30 hours after the first
    lands. The cheapest such chain wins. Without one, the flights take the tickets closest to the plan that
    still go forward in time, and the route says its dates do not chain."""
    items = _flight_items(legs, nights, start_at_home)
    if not items:  # no plane at all follows the plan by itself; a plane without fares cannot
        return not any(p.mode == "flight" for leg in legs for p in units(leg))
    for slack in DATE_SLACK_DAYS:  # the nights as planned first; a day more or less only when nothing fits
        if chosen := _chain(items, slack, start):
            for (_, flight, _), ticket in zip(items, chosen, strict=True):
                flight.ticket = ticket
            return True
    for (_, flight, _), ticket in zip(items, _closest(items, start), strict=True):
        flight.ticket = ticket
    return False


def _chain(items: list[tuple[int, Leg, str]], slack: int, start: date | None) -> list[Ticket] | None:
    """The cheapest chain of tickets with every leg within `slack` days of its planned day."""
    best: tuple[int, list[Ticket]] | None = None
    offset, first, _ = items[0]
    for anchor in first.flights.by_day or (first.flights.cheapest,):
        if anchor.day is None or (start and abs((anchor.day - start).days) > slack):
            continue
        trip_start = anchor.day - timedelta(days=offset)
        picks = [anchor]
        for days, flight, how in items[1:]:
            target = trip_start + timedelta(days=days)
            calendar = [t for t in flight.flights.by_day or (flight.flights.cheapest,) if t.day]
            if how == "after_flight":
                fits = [t for t in calendar if _layover_ok(picks[-1], t)]
            elif how == "after_land":
                fits = [t for t in calendar if 0 <= (t.day - target).days <= 1]
            else:
                fits = [t for t in calendar if abs((t.day - target).days) <= slack]
            if not fits:
                break
            picks.append(min(fits, key=lambda t: t.price))
        else:
            total = sum(t.price for t in picks)
            if best is None or total < best[0]:
                best = (total, picks)
    return best[1] if best else None


def _closest(items: list[tuple[int, Leg, str]], start: date | None) -> list[Ticket]:
    """No chain within the slack: from each first ticket, every next flight takes the ticket closest to its
    planned day that still flies after the one before. The start with the fewest days off the plan (then the
    cheapest) wins: a way home four days late beats the cheapest one three weeks late."""
    offset, first, _ = items[0]
    best: tuple[int, list[Ticket]] | None = None
    for anchor in first.flights.by_day or (first.flights.cheapest,):
        if anchor.day is None:
            continue
        trip_start = anchor.day - timedelta(days=offset)
        off = abs((anchor.day - start).days) if start else 0
        picks = [anchor]
        for days, flight, _ in items[1:]:
            target = trip_start + timedelta(days=days)
            calendar = [t for t in flight.flights.by_day or (flight.flights.cheapest,) if t.day]
            if not calendar:
                picks.append(flight.flights.cheapest)
                continue
            after = picks[-1].day or target
            pick = min(
                [t for t in calendar if t.day >= after] or calendar,
                key=lambda t: (abs((t.day - target).days), t.price),
            )
            off += abs((pick.day - target).days)
            picks.append(pick)
        cost = off * DAY_OFF_RUB + sum(t.price for t in picks)
        if best is None or cost < best[0]:
            best = (cost, picks)
    return best[1] if best else _forward(items)


def _forward(items: list[tuple[int, Leg, str]]) -> list[Ticket]:
    """The cheapest tickets that still fly in order: never a way home that leaves before the way out."""
    picks: list[Ticket] = []
    for _, flight, _ in items:
        calendar = sorted(flight.flights.by_day or (flight.flights.cheapest,), key=lambda t: t.price)
        after = picks[-1].day if picks and picks[-1].day else None
        later = [t for t in calendar if after is None or (t.day and t.day >= after)]
        picks.append((later or calendar)[0])
    return picks


async def rebuild_route(
    stops: list[Snapshot], brief: TripBrief, flights: Flights, origin: City | None, nights: int | None = None
) -> RoutePlan:
    """A route shown on an earlier turn, rebuilt from the same places in the same order, with fresh tickets."""
    q = RouteQuery(
        month=brief.month, kinds=brief.kinds, nights=nights or brief.nights_max or brief.nights_min
    )
    return await price_route(plan_of(stops, q), flights, origin, brief.month, by_land=bool(brief.by_land))


def _trip_value(plan: RoutePlan) -> float:
    """Price, hours and transfers of every leg in roubles, for choosing between two orders of the same cities."""
    return sum(leg_value(leg) for leg in plan.legs) + (0 if plan.dates_chained else UNCHAINED_RUB)


async def named_route(
    stops: list[Snapshot], q: RouteQuery, flights: Flights, origin: City | None
) -> RoutePlan:
    """The cities the user named. Unless the order is theirs, the order with the least travel and its reverse
    are both priced, and the better trip wins: home from Samarkand may cost three times home from Almaty."""
    sized = q.model_copy(update={"nights": q.nights or DEFAULT_NIGHTS})
    orders = [stops]
    if not q.order_fixed:
        km = [[_km(a, b) for b in stops] for a in stops]
        start = [km_between(origin.lat, origin.lon, s.place.lat, s.place.lon) if origin else 0 for s in stops]
        reach = [
            [i != j and _hop_ok(a, b, km[i][j], q.land, q.max_leg_km) for j, b in enumerate(stops)]
            for i, a in enumerate(stops)
        ]

        def cost(order: tuple[int, ...]) -> tuple[bool, float]:
            hops = list(pairwise(order))
            travel = start[order[0]] + start[order[-1]] + sum(km[a][b] for a, b in hops)
            return (not all(reach[a][b] for a, b in hops), travel)  # a hop nothing flies or drives goes last

        best = min(permutations(range(len(stops))), key=cost)
        orders = [[stops[i] for i in best], [stops[i] for i in reversed(best)]]
    plans = await asyncio.gather(
        *(price_route(plan_of(o, sized), flights, origin, q.month, by_land=q.land) for o in orders)
    )
    return min(plans, key=_trip_value)


async def find_routes(
    snapshots: list[Snapshot], q: RouteQuery, flights: Flights, origin: City | None
) -> list[RoutePlan]:
    """The best routes with real prices; at most one route per set of overlapping cities. Candidates get
    plain fares first; only the picked ones get smart ways and trains, which cost more requests."""
    # half of them different routes, not near copies of the best one (those would leave a single card after
    # the pick); the other half the best of the rest, so a near copy with a way home still gets its prices
    ranked = candidate_routes(snapshots, q, origin)
    candidates = _spread(ranked, PRICED_CANDIDATES // 2, (0.5,))
    candidates += [p for p in ranked if p not in candidates][: PRICED_CANDIDATES - len(candidates)]
    await asyncio.gather(
        *(price_route(plan, flights, origin, q.month, improve=False, by_land=q.land) for plan in candidates)
    )
    for plan in candidates:
        # no fare there from home this month, or none back home: a trip nobody can price yet
        ends = (plan.legs[0], plan.legs[-1]) if plan.legs and origin else ()
        if not plan.legs or any(leg.mode == "flight" and not leg.flights for leg in ends):
            plan.score -= 0.3
    # first routes that share no city, so the choice is a real choice; then near ones if there are too few
    picked = _spread(sorted(candidates, key=lambda p: -p.score), q.limit, (0.0, 0.5))
    # the picked ones in full: smarter ways, trains and buses (the fares are cached, so no new requests)
    await asyncio.gather(*(price_route(plan, flights, origin, q.month, by_land=q.land) for plan in picked))
    return picked


def _overlap(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b)


def _spread(plans: list[RoutePlan], count: int, most_shared: tuple[float, ...]) -> list[RoutePlan]:
    """Up to `count` plans in their order, each sharing at most the first share of its cities with those
    before it; the next share only when there are too few."""
    picked: list[RoutePlan] = []
    for share in most_shared:
        for plan in plans:
            ids = {s.place.id for s in plan.stops}
            fresh = all(_overlap(ids, {s.place.id for s in o.stops}) <= share for o in picked)
            if len(picked) < count and plan not in picked and fresh:
                picked.append(plan)
    return picked


def _day(s: Snapshot, month: int | None) -> int | None:
    day = s.climate.get(month, {}).get("air_max") if month else None
    return None if day is None else round(day)


def _leg_for_model(leg: Leg) -> dict:
    view = leg.view()
    if leg.parts:
        view["smarter_than_direct"] = leg.instead is not None
    if leg.guide and not leg.ticket:
        view["guide"] = guide_for_model(leg.guide)
    return view


def guide_for_model(guide: Ticket) -> str:
    when = f" ({guide.day:%d.%m})" if guide.day else ""
    return (
        f"{money(guide.price)}{when}: no fare cached for the trip's dates, so this is the best ticket of the "
        "nearest dates, a guide to the price; the live search for the trip's day is linked"
    )


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
                "visa": visa_text(s),
                "highlights": list(s.place.highlights[:2]),
            }
            for s, n in zip(plan.stops, plan.nights, strict=True)
        ],
        "legs": [_leg_for_model(leg) for leg in plan.legs],
        # one line per visa to get: the Schengen countries of the route share one
        "visas": [chip["text"] for chip in route_visas(list(zip(plan.stops, plan.nights, strict=True)))],
        "tickets_total": money(plan.total_rub) if plan.total_rub else None,
        "tickets_guide": money(plan.guide_rub) if plan.guide_rub else None,
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
                "lat": s.place.lat,
                "lon": s.place.lon,
                "kinds": list(s.place.kinds),
                "nights": nights,
                "day": round(climate["air_max"]) if climate and "air_max" in climate else None,
                "sea": round(climate["sea_temp"]) if climate and "sea_temp" in climate else None,
                "visa": visa_label(s.visa) if s.visa else VISA_LABELS.get(s.visa_rule, s.visa_rule),
                "visa_easy": s.visa_rule in EASY_VISA,
                "visa_info": visa_info(s),
                "highlights": list(s.place.highlights[:2]),
                "photo": place_photo(s.place.id),
            }
        )
    checked = [s.place.kids for s in plan.stops if s.place.verified]  # a route-map city has no kids rating
    kids = min(checked, key=["poor", "ok", "good"].index) if checked else None
    return {
        "type": "route",
        "id": plan.id,
        "name": plan.name,
        "month_in": MONTHS_IN[month - 1] if month else None,
        "month": MONTHS[month - 1] if month else None,
        "stops": stops,
        "legs": [leg.view() for leg in plan.legs],
        "visas": route_visas(list(zip(plan.stops, plan.nights, strict=True))),
        "total_rub": (plan.total_rub + plan.guide_rub) or None,
        "total_complete": plan.priced,
        "total_guided": plan.guide_rub > 0,
        "dates_chained": plan.dates_chained,
        "match": plan.match,
        "interests": plan.interests,
        "kids": KIDS_LABELS[kids] if kids else None,
        "why": why,
        "tradeoff": tradeoff,
    }
