"""One pick, the whole trip: tickets that follow the nights, then for every stop a hotel for this party, the
rides, the checks and the days, then the bill against the budget.

All of it is code, so a 23:40 landing or a budget overrun is found here; the model only explains the result.
"""

import asyncio
from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta

from app.catalog.catalog import Place
from app.catalog.search import MONTHS_IN, Snapshot
from app.flights import City, Flights, Ticket
from app.fx import rates
from app.hotels import HotelSource
from app.hotels.evidence import hotel_wishes
from app.money import CURRENCIES, money
from app.plan.checks import (
    AIRPORT_BEFORE,
    NIGHT_ENDS,
    Check,
    arrival_checks,
    at_hotel,
    departure_checks,
    keeps_room_to_flight,
)
from app.plan.hotels import WISH_WORDS, Hotel, HotelPick, Party, choose_hotel, hundreds, wishes_from
from app.plan.itinerary import LOGISTICS, Day, Item, Stay, plan_days
from app.plan.live_guide import guides
from app.plan.places import PlaceInfo, place_info
from app.plan.taxi import taxi
from app.plan.transfers import Transfer, transfer_to
from app.plan.trip import HOTEL_SPREAD, Costs, Move, StopPlan, TripPlan, day_text, span_text
from app.trip.brief import TripBrief, night_range, price_level
from app.trip.legs import arriving, leaving, units
from app.trip.routes import DEFAULT_NIGHTS, ROAD_DETOUR, Leg, RoutePlan, price_route, split_nights

HOME_LEAVES = time(9)  # a trip by land from home starts in the morning
GROUND_LEAVES = time(10, 30)  # a hop between cities starts after breakfast and check-out
NOMINAL_ARRIVAL = time(15)  # without a ticket on the plan's dates the arrival time is unknown
NOMINAL_LEAVE = time(12)
START_DAY = 10  # with a month and no tickets the trip starts on the 10th
LEAD_DAYS = 14  # and never sooner than two weeks from today
SEA_WARM_C = 22
GROUND_RUB_PER_KM = 5  # a bus or train seat, per person: an estimate, never a quote
GUIDE_WAIT_S = 15.0  # a city's live guide not found by then: the plan keeps what the seed has
TAXI_WAIT_S = 12.0  # a city's taxi fare not found by then: the ride is the estimate by the kilometre
INFANT_FARE = 0.1  # under two flies on a lap for about a tenth of the fare
INFANT_AGE = 2
UNKNOWN_CHILD_AGE = 7
FLIGHT_WISHES = ("прям", "без пересад", "перел", "лететь")


@dataclass(frozen=True)
class _Arrival:
    reached: datetime
    move: Move | None
    landing: Ticket | None
    items: list[tuple[date, str, Item]]


@dataclass(frozen=True)
class _Departure:
    check_out: date
    leave: datetime | None
    move: Move | None
    back: Ticket | None
    items: list[tuple[date, str, Item]]


def party_of(brief: TripBrief) -> Party:
    ages = list(brief.children_ages or [])
    ages += [UNKNOWN_CHILD_AGE] * max(0, (brief.children or 0) - len(ages))
    return Party(brief.adults or 2, tuple(ages))


def _start(brief: TripBrief, today: date) -> date:
    if brief.date_from:
        return brief.date_from
    earliest = today + timedelta(days=LEAD_DAYS)
    if not brief.month:
        return earliest
    start = date(earliest.year, brief.month, START_DAY)
    return start if start >= earliest else date(earliest.year + 1, brief.month, START_DAY)


def _flight_text(ticket: Ticket) -> str:
    stops = "прямой" if ticket.transfers == 0 else f"пересадок: {ticket.transfers}"
    return f"{ticket.airline} {ticket.flight_number}, {stops}, {round(ticket.duration_min / 60 * 2) / 2:g} ч"


def _ride_text(ride: Transfer | None) -> str | None:
    if ride is None:
        return None
    way = "катер" if ride.mode == "boat" else "такси"
    return f"{way}, около {ride.minutes} мин, {money(ride.price_rub)}"


def _ground_rub(leg: Leg) -> int:
    """A real train or bus fare when one was found, else the estimate by distance."""
    if leg.ground_rub is not None:
        return leg.ground_rub
    return hundreds(leg.km * ROAD_DETOUR * GROUND_RUB_PER_KM)


def _smart_check(leg: Leg) -> Check | None:
    """Says how a smart way goes, part by part, and what it saves against the direct flight."""
    if not leg.parts:
        return None
    steps = []
    for part in leg.parts:
        if part.ticket:
            steps.append(f"рейс {part.origin} → {part.destination} ({_flight_text(part.ticket)})")
        elif part.ground:
            best = part.ground.best
            steps.append(f"{best.name} {part.origin} → {part.destination}, около {part.hours:g} ч")
        else:
            steps.append(f"по земле {part.origin} → {part.destination}, около {part.hours:g} ч")
    text = "; затем ".join(steps).capitalize() + "."
    if leg.instead and leg.price_rub is not None:
        text += f" Прямой вариант стоил {money(leg.instead['price_rub'])} с пересадками: {leg.instead['transfers']}."
    return Check("info", f"{leg.origin} → {leg.destination} через {leg.via}", text, kind="move")


def _unticketed(leg: Leg) -> str:
    """What the day says of a flight with no ticket on it: the fare to plan with and where the day's fares are."""
    if leg.ticket and leg.ticket.day:
        return f"ближайший билет {day_text(leg.ticket.day)} за {money(leg.ticket.price)}, на этот день: в поиске Aviasales"
    if leg.guide:
        return f"ориентир {money(leg.guide.price)} по ближайшим датам, цена на этот день: в поиске Aviasales"
    return "цены на этот день: в поиске Aviasales"


def _key(moment: datetime) -> tuple[date, str]:
    return moment.date(), moment.strftime("%H:%M")


def _arrival(
    leg: Leg | None, fixed: bool, nominal: date, cursor: datetime | None, info: PlaceInfo,
    hotel_name: str, ride: Transfer | None,
) -> _Arrival:  # fmt: skip
    check_in = f"Заселение: {hotel_name}"
    landing = (
        leg.ticket if fixed and leg and leg.mode == "flight" and leg.ticket and leg.ticket.arrives else None
    )
    if landing:
        reached = at_hotel(landing, info, ride.minutes if ride else 0)
        lands = info.local(landing.arrives)
        flight = Item("flight", f"Перелёт {leg.origin} → {leg.destination}", _key(landing.departs)[1],
                      f"{_flight_text(landing)}, прилёт в {lands:%H:%M}")  # fmt: skip
        items = [
            (*_key(landing.departs), flight),
            (*_key(lands), Item("transfer", "Трансфер в отель", f"{lands:%H:%M}", _ride_text(ride))),
            (*_key(reached), Item("hotel", check_in, f"{reached:%H:%M}")),
        ]
        return _Arrival(reached, Move(leg, landing.departs, lands), landing, items)
    if leg and leg.mode == "ground":
        leaves = cursor or datetime.combine(nominal, HOME_LEAVES, info.tz)
        reached = (leaves + timedelta(hours=leg.hours)).astimezone(info.tz)
        move = Move(leg, leaves, reached, _ground_rub(leg))
        items = [(*_key(reached), Item("hotel", check_in, f"{reached:%H:%M}"))]
        if cursor is None:  # from home; a hop between stops is listed by the stop it leaves
            note = f"около {leg.hours:g} ч: поезд, автобус или машина"
            items.insert(
                0,
                (
                    *_key(leaves),
                    Item("move", f"Дорога {leg.origin} → {leg.destination}", f"{leaves:%H:%M}", note),
                ),
            )
        return _Arrival(reached, move, None, items)
    reached = datetime.combine(nominal, NOMINAL_ARRIVAL, info.tz)
    items = [
        (
            reached.date(),
            "00:00",
            Item("hotel", check_in, None, "время заселения: по рейсу, который выберете"),
        )
    ]
    if leg:
        items.insert(0, (reached.date(), "00:00", Item("flight", f"Перелёт {leg.origin} → {leg.destination}", None,
                                                       _unticketed(leg))))  # fmt: skip
    return _Arrival(reached, Move(leg) if leg else None, None, items)


def _departure(
    leg: Leg | None, fixed: bool, check_in: date, nights: int, info: PlaceInfo, abroad: bool,
    ride: Transfer | None, check_out_at: time, last: bool,
) -> _Departure:  # fmt: skip
    back = (
        leg.ticket if fixed and leg and leg.mode == "flight" and leg.ticket and leg.ticket.departs else None
    )
    if back:
        flight = info.local(back.departs)
        go = flight - AIRPORT_BEFORE[abroad] - timedelta(minutes=ride.minutes if ride else 0)
        keeps_room = keeps_room_to_flight(go, flight, last)
        out = go if keeps_room else min(go, datetime.combine(go.date(), check_out_at, go.tzinfo))
        items = [
            (*_key(out), Item("hotel", "Выезд из отеля", f"{out:%H:%M}")),
            (*_key(go), Item("transfer", "Трансфер в аэропорт", f"{go:%H:%M}", _ride_text(ride))),
        ]
        if last:  # a hop between stops is listed by the stop it flies to
            items.append((*_key(flight), Item("flight", f"Перелёт {leg.origin} → {leg.destination}", f"{flight:%H:%M}", _flight_text(back))))  # fmt: skip
        leaves = flight.date() if keeps_room else go.date()
        return _Departure(max(leaves, check_in + timedelta(days=1)), go, None, back, items)
    check_out = check_in + timedelta(days=nights)
    if leg is None:
        return _Departure(check_out, None, None, None, [])
    if leg.mode == "ground":
        leave = datetime.combine(check_out, GROUND_LEAVES, info.tz)
        note = f"около {leg.hours:g} ч по земле: поезд, автобус или такси, около {money(_ground_rub(leg))} на человека"
        items = [
            (check_out, "10:00", Item("hotel", "Выезд из отеля", "10:00")),
            (*_key(leave), Item("move", f"Переезд {leg.origin} → {leg.destination}", f"{leave:%H:%M}", note)),
        ]
        move = Move(leg, leave, leave + timedelta(hours=leg.hours), _ground_rub(leg))
        return _Departure(check_out, leave, move, None, items)
    leave = datetime.combine(check_out, NOMINAL_LEAVE, info.tz)
    items = [
        (check_out, "12:00", Item("hotel", "Выезд из отеля", "12:00")),
        (check_out, "23:59", Item("flight", f"Перелёт {leg.origin} → {leg.destination}", None, _unticketed(leg))),
    ]  # fmt: skip
    return _Departure(check_out, leave, None, None, items)


def _with_nights(pick: HotelPick, nights: int) -> HotelPick:
    return replace(
        pick,
        best=replace(pick.best, nights=nights),
        alternatives=[replace(a, nights=nights) for a in pick.alternatives],
    )


def _ticket_checks(route: RoutePlan, fixed: bool, brief: TripBrief) -> list[Check]:
    """What to know about the tickets. Never «no tickets»: a month the cache has no fare for is priced by the
    best ticket of the nearest dates, and the live search on Aviasales has the day's fares."""
    flown = [leg for leg in route.legs if leg.mode == "flight"]
    when = f"в {MONTHS_IN[brief.month - 1]}" if brief.month else "на эти даты"
    checks = []
    if guided := [leg for leg in flown if not leg.flights and leg.guide]:
        legs = "; ".join(f"{leg.origin} → {leg.destination} от {money(leg.guide.price)}" for leg in guided)
        text = f"Цен {when} в кэше Aviasales пока нет, поэтому перелёт посчитан по лучшему билету ближайших дат: {legs}. Точная цена на ваш день в живом поиске Aviasales, ссылка у рейса."
        checks.append(Check("info", "Цена перелёта по ориентиру", text, kind="tickets"))
    if blind := [leg for leg in flown if not leg.flights and not leg.guide]:
        names = ", ".join(f"{leg.origin} → {leg.destination}" for leg in blind)
        text = f"{names}: цены на эти даты есть в живом поиске Aviasales, ссылка у рейса. В итог этот перелёт пока не входит."
        checks.append(Check("info", "Цена в поиске Aviasales", text, kind="tickets"))
    for leg in flown:
        if leg.pricey:
            text = f"{leg.origin} → {leg.destination}: {money(leg.ticket.price)}, а обычно на этом направлении около {money(leg.usual_rub)}. Это лучший билет, который сходится с датами поездки; если сдвинуть её на несколько дней, перелёт выйдет дешевле."
            checks.append(Check("warn", "Билет дороже обычного", text, kind="tickets"))
    if guided or blind:
        return checks
    if flown and not fixed:
        text = "Билеты есть, но ни один набор рейсов не сходится с числом ночей. Цены ниже ориентировочные, самые дешёвые за месяц: можно сдвинуть даты или число ночей на день."
        return [Check("warn", "Билеты не сходятся по датам", text, kind="tickets"), *checks]
    first = next((leg.ticket for leg in flown if leg.ticket), None)
    if brief.date_from and first and first.day and first.day != brief.date_from:
        text = f"На {day_text(brief.date_from)} подходящих рейсов нет, ближайший {day_text(first.day)}: план сдвинут на этот день."
        checks.insert(0, Check("info", f"Вылет {day_text(first.day)}", text, kind="tickets"))
    return checks


def _budget_check(costs: Costs, stops: list[StopPlan], fixed: bool) -> list[Check]:
    if not costs.budget:
        return []
    if not costs.over_by and not costs.flights_complete:
        text = f"Без перелёта, цена которого пока только в поиске Aviasales: {money(costs.total)} из {money(costs.budget)}."
        return [Check("info", "Бюджет", text, kind="budget")]
    guide = " Перелёт посчитан по ориентиру ближайших дат." if costs.flights_guide else ""
    if not costs.over_by:
        text = f"Вся поездка {money(costs.total)} из {money(costs.budget)}.{guide}"
        return [Check("ok", "В бюджете", text, kind="budget")]
    text = f"Вся поездка выходит {money(costs.total)}, это на {money(costs.over_by)} больше бюджета.{guide}"
    savings = [
        (s.pick.best.total_rub - a.total_rub, a.hotel.name)
        for s in stops
        for a in s.pick.alternatives
        if a.total_rub < s.pick.best.total_rub
    ]
    if savings:
        saved, name = max(savings)
        text += f" Отель «{name}» дешевле на {money(saved)}."
    if fixed and costs.flights and not costs.flights_guide:
        text += " Билеты в этой сумме уже самые выгодные из тех, что сходятся с датами: дешевле перелёт выйдет, только если сдвинуть поездку."
    return [Check("warn", "Дороже бюджета", text, kind="budget")]


def _wishes(brief: TripBrief, stops: list[StopPlan], moves: list[Move]) -> tuple[list[str], list[str]]:
    words = brief.wishes or []
    known = (*(w for keys in WISH_WORDS.values() for w in keys), *FLIGHT_WISHES)
    seen = (h for s in stops for h in (s.pick.best.hotel, *(a.hotel for a in s.pick.alternatives)))
    checked = {e.wish for h in (*seen, *(h for s in stops for h, _ in s.pick.excluded)) for e in h.evidence}
    not_checked = [w for w in words if w not in checked and not any(k in w.casefold() for k in known)]
    many = len(stops) > 1
    unmet = [f"{s.place.name}: {u}" if many else u for s in stops for u in s.pick.unmet]
    wants_direct = any(k in w.casefold() for w in words for k in ("прям", "без пересад"))
    if wants_direct and any(m.leg.ticket and m.leg.ticket.transfers for m in moves if m.departs):
        unmet.append("Прямого рейса на эти даты нет, лучший вариант с пересадкой")
    return unmet, not_checked


def _costs(route: RoutePlan, party: Party, stops: list[StopPlan], brief: TripBrief) -> Costs:
    infants = sum(1 for a in party.children_ages if a < INFANT_AGE)
    seats = party.guests - infants + INFANT_FARE * infants
    every = [u for leg in route.legs for u in units(leg)]  # a smart way pays for each of its parts
    flown = [u for u in every if u.mode == "flight"]
    budget = (
        CURRENCIES[brief.budget_currency or "RUB"].to_rub(brief.budget_total) if brief.budget_total else None
    )
    return Costs(
        # a flight with no fare on its day counts at the best fare of the nearest dates, marked as a guide
        flights=round(sum(fare.price for leg in flown if (fare := leg.ticket or leg.guide)) * seats),
        flights_guide=round(sum(leg.guide.price for leg in flown if leg.guide and not leg.ticket) * seats),
        hotels=sum(s.pick.best.total_rub for s in stops),
        transfers=sum(s.transfers_rub for s in stops),
        ground=sum(_ground_rub(u) for u in every if u.mode == "ground") * party.guests,
        guests=party.guests,
        flights_complete=all(leg.ticket or leg.guide for leg in flown),
        budget=budget,
        **_hotel_range(stops),
    )


def _hotel_range(stops: list[StopPlan]) -> dict:
    """The hotels' share of the range: down to the cheapest hotel offered, with the estimate's spread."""
    estimate = any(s.pick.best.rate.estimate or not s.pick.best.hotel.real for s in stops)
    low_k, high_k = HOTEL_SPREAD if estimate else (1.0, 1.0)
    low = sum(min([s.pick.best.total_rub, *(a.total_rub for a in s.pick.alternatives)]) for s in stops)
    high = sum(s.pick.best.total_rub for s in stops)
    return {
        "hotels_low": round(low * low_k),
        "hotels_high": round(high * high_k),
        "hotels_estimate": estimate,
    }


def _days(
    per_stop: list[tuple[StopPlan, list[Day], list[tuple[date, str, Item]]]], by_land: bool
) -> list[Day]:
    items: dict[date, list[tuple[str, Item]]] = defaultdict(list)
    titles: dict[date, tuple[str, str]] = {}
    for stop, days, travel in per_stop:
        for day in days:
            items[day.date] += [(i.time or "00:00", i) for i in day.items]
            shared = day.date in titles
            titles[day.date] = (
                (f"Переезд в {stop.place.name}", stop.place.id) if shared else (day.title, stop.place.id)
            )
        for when, key, item in travel:
            items[when].append((key, item))
    dates = sorted(items)
    result = []
    for d in dates:
        ordered = [i for _, i in sorted(items[d], key=lambda pair: pair[0])]
        title, place_id = titles.get(d, ("В пути", per_stop[-1][0].place.id))
        if all(i.kind in LOGISTICS for i in ordered):
            title = "Вылет" if d == dates[0] else "Дорога домой" if d == dates[-1] else title
        elif d == dates[0] and by_land:
            title = "Дорога и первый вечер"
        result.append(Day(d, title, place_id, ordered))
    return result


def changes_since(previous: dict | None, plan: TripPlan) -> list[str]:
    if not previous or previous.get("id") != plan.id:
        return []
    changes = []
    if (previous["check_in"], previous["check_out"]) != (plan.start.isoformat(), plan.end.isoformat()):
        was = span_text(date.fromisoformat(previous["check_in"]), date.fromisoformat(previous["check_out"]))
        changes.append(f"Даты: {span_text(plan.start, plan.end)} вместо {was}")
    for s in plan.stops:
        old = previous.get("hotels", {}).get(s.place.id)
        new = s.pick.best.hotel
        if old and old["id"] != new.id:
            changes.append(f"Отель в {s.place.name}: «{new.name}» вместо «{old['name']}»")
    if previous.get("guests") != plan.party.guests:
        changes.append(f"Едут {plan.party.guests} вместо {previous.get('guests')}")
    was_total = previous.get("total_rub") or 0
    if abs(plan.costs.total - was_total) >= max(1000, was_total // 100):
        changes.append(f"Стоимость: {money(plan.costs.total)} вместо {money(was_total)}")
    return changes


async def assemble(
    stops: list[Snapshot],
    brief: TripBrief,
    flights: Flights,
    origin: City | None,
    today: date,
    prefer: dict[str, str] | None = None,
    previous: dict | None = None,
    hotels: "HotelSource | None" = None,
) -> TripPlan:
    hotels = hotels or HotelSource()
    party, wishes, level = party_of(brief), wishes_from(brief.wishes), price_level(brief)
    asked = hotel_wishes(brief.wishes)
    total_nights = night_range(brief)[1] or DEFAULT_NIGHTS
    route = RoutePlan(stops, split_nights(total_nights, stops), 0.0, 0, [])
    await price_route(route, flights, origin, brief.month, start=brief.date_from, by_land=bool(brief.by_land))
    fixed, home = route.dates_chained, origin is not None
    legs = route.legs
    first = next(((j, leg) for j, leg in enumerate(legs) if leg.mode == "flight" and leg.ticket), None)
    if fixed and first and first[1].ticket.day:
        j = first[0]
        start = first[1].ticket.day - timedelta(days=sum(route.nights[: j if home else j + 1]))
    else:
        start = _start(brief, today)
    outbound = legs[0].ticket if home and fixed and legs else None
    # the flight home lands in the zone it left from on the way out
    home_tz = outbound.departs.tzinfo if outbound and outbound.departs else None

    checks = _ticket_checks(route, fixed, brief)
    checks += [c for leg in route.legs if (c := _smart_check(leg))]
    nominals = [start + timedelta(days=sum(route.nights[:i])) for i in range(len(route.stops))]

    async def hotels_at(
        i: int, place: Place, check_in: date | None = None, nights: int | None = None
    ) -> list[Hotel]:
        found = await hotels.hotels(place, check_in or nominals[i], nights or route.nights[i], party)
        return await hotels.checked(place, found, asked, party, level, (prefer or {}).get(place.id))

    # the hotels and the cities' taxi fares at once; the fares are usually cached since the cards were shown
    # usually all cached since the cards were shown: the guide of a city found live, its taxi fare
    stays, fares, found_guides = await asyncio.gather(
        asyncio.gather(*(hotels_at(i, s.place) for i, s in enumerate(route.stops))),
        taxi().fares([s.place.id for s in route.stops], TAXI_WAIT_S),
        asyncio.gather(*(guides().guide(s.place, GUIDE_WAIT_S) for s in route.stops)),
    )
    fare_rubs = {pid: await rates().to_rub(f.amount, f.currency) for pid, f in fares.items() if f}
    base_checks = checks
    for priced in (False, True):
        checks, planned, per_stop, stayed = list(base_checks), [], [], []
        moves: dict[int, Move] = {}
        cursor: datetime | None = None
        for i, s in enumerate(route.stops):
            place, info = s.place, place_info(s.place.id)
            j_in, j_out = (i, i + 1) if home else (i - 1, i)
            # a smart way is seen from each city by its own end: a train out of here, a flight landing there
            leg_in = arriving(legs[j_in]) if 0 <= j_in < len(legs) else None
            leg_out = leaving(legs[j_out]) if 0 <= j_out < len(legs) else None
            nominal = nominals[i]
            month = nominal.month
            pick = choose_hotel(stays[i], party, wishes, level, route.nights[i], (prefer or {}).get(place.id))
            hotel = pick.best.hotel
            fare, fare_rub = fares.get(place.id), fare_rubs.get(place.id)
            ride_in = (
                transfer_to(hotel, place, info, party, fare, fare_rub)
                if leg_in and leg_in.mode == "flight"
                else None
            )
            ride_out = (
                transfer_to(hotel, place, info, party, fare, fare_rub)
                if leg_out and leg_out.mode == "flight"
                else None
            )
            arrival = _arrival(leg_in, fixed, nominal, cursor, info, hotel.name, ride_in)
            check_in = (arrival.reached - NIGHT_ENDS).date()
            if i < len(route.stops) - 1:
                abroad = route.stops[i + 1].place.country.code != place.country.code
            else:
                abroad = place.country.name != origin.country if origin else not place.domestic
            last = i == len(route.stops) - 1
            departure = _departure(
                leg_out, fixed, check_in, route.nights[i], info, abroad, ride_out, hotel.check_out, last
            )
            pick = _with_nights(pick, (departure.check_out - check_in).days)
            stayed.append((check_in, (departure.check_out - check_in).days))
            stop = StopPlan(s, check_in, departure.check_out, pick, found_guides[i], ride_in, ride_out)
            if arrival.landing:
                checks += arrival_checks(arrival.landing, hotel, info, ride_in.minutes if ride_in else 0)
            if departure.back:
                checks += departure_checks(
                    departure.back, hotel, info, ride_out.minutes if ride_out else 0, abroad, last
                )
            if leg_out and leg_out.mode == "ground" and i < len(route.stops) - 1:
                text = f"Около {leg_out.hours:g} ч по земле: поезд, автобус или такси после завтрака. Цена оценочная, около {money(_ground_rub(leg_out))} на человека."
                checks.append(
                    Check("info", f"Переезд {leg_out.origin} → {leg_out.destination}", text, kind="move")
                )
            if arrival.move and leg_in:
                moves[j_in] = replace(arrival.move, leg=legs[j_in])  # the whole leg, its parts included
            if departure.move and leg_out:
                moves.setdefault(j_out, replace(departure.move, leg=legs[j_out]))
            if departure.back and leg_out:
                lands = (
                    departure.back.arrives.astimezone(home_tz) if departure.back.arrives and home_tz else None
                )
                moves.setdefault(j_out, Move(legs[j_out], departure.back.departs, lands))
            climate = s.climate.get(month, {})
            stay = Stay(
                guide=stop.guide,
                check_in=check_in,
                check_out=departure.check_out,
                arrive=arrival.reached,
                leave=departure.leave,
                hotel_at=(hotel.lat, hotel.lon),
                sea="sea" in place.kinds,
                sea_warm=(climate.get("sea_temp") or 0) >= SEA_WARM_C,
                all_inclusive=pick.best.rate.meal == "all_inclusive",
            )
            per_stop.append((stop, plan_days(stay, party), [*arrival.items, *departure.items]))
            planned.append(stop)
            cursor = departure.leave
        # live rates hold for the dates they were asked for: when the stay moved (a night flight lands the next
        # morning), the hotels are priced again for the nights really spent there, and the stops laid out again
        moved = [
            i
            for i, (check_in, nights) in enumerate(stayed)
            if any(h.provider for h in stays[i]) and (check_in, nights) != (nominals[i], route.nights[i])
        ]
        if priced or not moved:
            break
        again = await asyncio.gather(*(hotels_at(i, route.stops[i].place, *stayed[i]) for i in moved))
        stays = [again[moved.index(i)] if i in moved else found for i, found in enumerate(stays)]

    # a flight with no ticket on the plan's day links the live search on that day
    for j, leg in enumerate(legs):
        if leg.mode == "flight" and not leg.parts and not (fixed and leg.ticket) and planned:
            k = j if home else j + 1
            leg.day = planned[k].check_in if k < len(planned) else planned[-1].check_out
    costs = _costs(route, party, planned, brief)
    checks += _budget_check(costs, planned, fixed)
    all_moves = [moves.get(j, Move(leg)) for j, leg in enumerate(legs)]
    unmet, not_checked = _wishes(brief, planned, all_moves)
    by_land = bool(legs) and home and legs[0].mode == "ground"
    plan = TripPlan(
        id=route.id,
        name=route.name,
        party=party,
        stops=planned,
        moves=all_moves,
        checks=checks,
        days=_days(per_stop, by_land),
        costs=costs,
        dates_fixed=fixed,
        unmet=unmet,
        wishes_not_checked=not_checked,
    )
    return replace(plan, changes=changes_since(previous, plan))
