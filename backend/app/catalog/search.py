"""Destination search: exact filters on facts, plus the near misses with the reason they missed.

The filters run in code, never in the model, so «море от 24 °C» or «перелёт до 6 часов» is right every time.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.catalog import (
    KIDS_LABELS,
    KIND_LABELS,
    PRICE_LABELS,
    RAIL_ORIGIN,
    VISA_LABELS,
    Catalog,
    Kind,
    Place,
)
from app.facts.resolve import Resolution
from app.facts.service import Resolved, resolve_entities
from app.flights import City, Flights, RouteFlights, city, current_origin
from app.money import current_currency, money
from app.photos import place_photo
from app.visas import VisaRule, fees, rule_for
from app.visas import label as visa_label
from app.visas import sentence as visa_sentence
from app.visas import view as visa_view

MONTHS = [
    "январь",
    "февраль",
    "март",
    "апрель",
    "май",
    "июнь",
    "июль",
    "август",
    "сентябрь",
    "октябрь",
    "ноябрь",
    "декабрь",
]
MONTHS_IN = [
    "январе",
    "феврале",
    "марте",
    "апреле",
    "мае",
    "июне",
    "июле",
    "августе",
    "сентябре",
    "октябре",
    "ноябре",
    "декабре",
]
CLIMATE_ATTRIBUTES = ("air_max", "air_min", "sea_temp", "rain_days")
NO_VISA = {"none", "visa_free"}
EASY_VISA = NO_VISA | {"on_arrival", "evisa", "eta"}
MAX_NEAR_MISSES = 6

SOURCES_NOTE = {
    "климат": "Open-Meteo (ERA5), средние за 2020–2024",
    "море": "Open-Meteo Marine, средние за 2021–2024",
    "перелёты": "Aviasales (Travelpayouts): самые дешёвые билеты, найденные за последние дни, в одну сторону "
    "на человека; не живой поиск, цена может измениться",
    "поезда": "оценка команды, только из Москвы",
    "визы, уровень цен, дети": "оценка команды 1surak на 25.10.2026, не сверено с официальными источниками",
}


class SearchQuery(BaseModel):
    month: int | None = Field(
        None, ge=1, le=12, description="Travel month 1-12. Required for temperature filters."
    )
    kinds: list[Kind] | None = Field(
        None, description="Wanted kinds of trip, any of them matches: sea, mountains, city, nature, ski."
    )
    min_sea_temp: float | None = Field(None, ge=0, le=35, description="Minimum average sea temperature, °C.")
    min_air_temp: float | None = Field(
        None, ge=-30, le=45, description="Minimum average daytime air temperature, °C."
    )
    max_flight_hours: float | None = Field(
        None, gt=0, le=20, description="Longest acceptable flight from Moscow, h."
    )
    direct_only: bool = Field(False, description="Only places with direct flights from the user's city.")
    max_ticket: int | None = Field(
        None, gt=0, description="Most a one-way ticket per person may cost, in the user's currency."
    )
    without_flight: bool = Field(False, description="Only places reachable by train from Moscow.")
    visa: Literal["any", "no_visa", "easy"] = Field(
        "any", description="no_visa: domestic or visa-free; easy: also visa on arrival or e-visa."
    )
    with_kids: bool = Field(False, description="Travelling with small children.")
    kids_ages: list[int] | None = Field(
        None, description="Children's ages if the user named them. Leave empty when they didn't: don't guess."
    )
    max_price_level: int | None = Field(None, ge=1, le=3, description="1 budget, 2 mid-range, 3 expensive.")
    region: Literal["any", "russia", "abroad"] = Field(
        "any", description="russia: within the user's own country (the departure city's); abroad: outside it."
    )
    countries: list[str] | None = Field(
        None, description="Only these countries, names in Russian as the user said them: ['Турция']."
    )
    exclude: list[str] = Field(
        default_factory=list, description="Destination ids to leave out, e.g. rejected ones."
    )
    limit: int = Field(5, ge=1, le=10)

    @model_validator(mode="after")
    def _month_for_temperatures(self):
        if self.month is None and (self.min_sea_temp is not None or self.min_air_temp is not None):
            raise ValueError("month is required when filtering by sea or air temperature")
        return self


@dataclass
class Snapshot:
    """One place with every fact the search needs, already resolved across sources."""

    place: Place
    climate: dict[int, dict[str, float]] = field(default_factory=dict)
    flights: RouteFlights | None = None  # real tickets from the user's city, filled per search
    train_min: float | None = None
    visa_rule: str = "visa_required"
    visa_days: float | None = None
    visa_note: str | None = None
    # the rule for the traveller's own passport (the departure country's), from the Passport Index
    visa: VisaRule | None = None
    flags: list[str] = field(default_factory=list)
    # no cached ticket: the live search on Aviasales, and two tickets through the country's main airport
    search_link: str | None = None
    via: dict | None = None

    @property
    def flight_min(self) -> int | None:
        return self.flights.duration_min if self.flights else None

    @property
    def direct(self) -> bool | None:
        return None if self.flights is None else self.flights.direct is not None

    @property
    def ticket_rub(self) -> int | None:
        return self.flights.cheapest.price if self.flights else None


def _note_quality(snapshot: Snapshot, label: str, resolution: Resolution) -> None:
    if resolution.conflict:
        others = ", ".join(f"{a.source}: {a.value}" for a in resolution.alternatives)
        snapshot.flags.append(f"{label}: источники расходятся ({others})")
    if resolution.stale:
        snapshot.flags.append(f"{label}: данные устарели, на {resolution.chosen.fetched_at.date()}")


def _value(snapshot: Snapshot, facts: Resolved, attribute: str, label: str, period: str | None = None):
    resolution = facts.get((attribute, period))
    if resolution is None:
        return None
    _note_quality(snapshot, label, resolution)
    return resolution.chosen.value


def build_snapshot(place: Place, place_facts: Resolved, route: Resolved, country: Resolved) -> Snapshot:
    snapshot = Snapshot(place=place)
    for month in range(1, 13):
        values = {
            attribute: value
            for attribute in CLIMATE_ATTRIBUTES
            if (value := _value(snapshot, place_facts, attribute, f"{attribute} m{month}", f"m{month}"))
            is not None
        }
        if values:
            snapshot.climate[month] = values
    snapshot.train_min = _value(snapshot, route, "train_duration", "поезд")
    snapshot.visa_rule = _value(snapshot, country, "visa_rule", "виза") or place.country.visa
    snapshot.visa_days = _value(snapshot, country, "visa_days", "срок без визы")
    snapshot.visa_note = _value(snapshot, country, "visa_note", "виза")
    if rule := rule_for(place.country.code):  # the traveller's passport beats the team's note for Russians
        snapshot.visa = rule
        snapshot.visa_rule, snapshot.visa_days = rule.code, rule.days
        if rule.passport != "RU":
            snapshot.visa_note = None
    return snapshot


async def load_snapshots(db: AsyncSession, catalog: Catalog, now: datetime) -> list[Snapshot]:
    places = catalog.places
    place_facts = await resolve_entities(db, "place", [p.qid for p in places], now)
    routes = await resolve_entities(db, "route", [p.rail_route_id for p in places], now)
    countries = await resolve_entities(db, "country", sorted({p.country.code for p in places}), now)
    return [
        build_snapshot(p, place_facts[p.qid], routes[p.rail_route_id], countries[p.country.code])
        for p in places
    ]


async def with_flights(
    snapshots: list[Snapshot],
    flights: Flights,
    origin: str,
    month: int | None,
    q: "SearchQuery | None" = None,
) -> list[Snapshot]:
    """Real tickets from the user's city to every place the query could pick, fetched in parallel.
    Train times are measured from Moscow, so from anywhere else they are dropped rather than misleading."""
    wanted = [s for s in snapshots if s.place.airport and (q is None or in_scope(s, q))]
    found = await flights.routes(origin, sorted({s.place.airport for s in wanted}), month)
    for s in snapshots:
        s.flights = found.get(s.place.airport) if s.place.airport else None
        if origin != RAIL_ORIGIN:
            s.train_min = None
    return snapshots


def _hours(minutes: float | None) -> float | None:
    return None if minutes is None else round(minutes / 60 * 2) / 2  # nearest half hour


def home_country() -> str:
    """The user's own country, from the departure city: «abroad» from Astana means outside Kazakhstan."""
    home = city(current_origin.get())
    return home.country_code if home and home.country_code else "RU"


def in_scope(s: Snapshot, q: SearchQuery) -> bool:
    """The kind of trip and the region define what the user asked for, so a miss here is not a near miss."""
    place = s.place
    if q.kinds and not set(q.kinds) & set(place.kinds):
        return False
    if q.min_sea_temp is not None and "sea" not in place.kinds:  # a sea temperature implies a sea trip
        return False
    if q.region != "any" and (place.country.code == home_country()) != (q.region == "russia"):
        return False
    if q.countries and place.country.name.casefold() not in {c.strip().casefold() for c in q.countries}:
        return False
    excluded = {e.strip().casefold() for e in q.exclude}
    return place.id not in excluded and place.name.casefold() not in excluded


@dataclass(frozen=True)
class Miss:
    """One constraint a place misses. `gap` says how far off it is, so the closest misses come first."""

    reason: str
    kind: str
    gap: float


MISSING_DATA_GAP = 2.0
MAX_NEAR_GAP = 2.5  # beyond this a miss is a different trip, not a near one (no train, sea at 7 °C)


def _temp(value: float, threshold: float) -> str:
    # 23.6 against «от 24» must not read as «около 24 °C, нужно от 24 °C»
    return f"{value:.1f}" if round(value) >= threshold else f"{value:.0f}"


def _climate_miss(q: SearchQuery, value: float | None, threshold: float, what: str, kind: str) -> Miss | None:
    if value is None:
        return Miss(f"нет данных: {what}", kind, MISSING_DATA_GAP)
    if value >= threshold:
        return None
    month = MONTHS_IN[q.month - 1]
    label = "море" if kind == "sea" else "днём"
    reason = f"{label} в {month} около {_temp(value, threshold)} °C, нужно от {threshold:g} °C"
    return Miss(reason, kind, (threshold - value) / 3)


def failures(s: Snapshot, q: SearchQuery, origin: str = "из вашего города") -> list[Miss]:
    """Every adjustable constraint this place misses, in words the agent can pass on."""
    place, misses = s.place, []
    month_climate = s.climate.get(q.month, {}) if q.month else {}
    if q.min_sea_temp is not None:
        misses.append(
            _climate_miss(q, month_climate.get("sea_temp"), q.min_sea_temp, "температура моря", "sea")
        )
    if q.min_air_temp is not None:
        misses.append(_climate_miss(q, month_climate.get("air_max"), q.min_air_temp, "погода", "air"))

    if q.without_flight:
        if s.train_min is None:
            misses.append(Miss("без самолёта не добраться", "train", 3.0))
    else:
        if q.max_flight_hours is not None:
            if s.flight_min is None:
                misses.append(Miss(f"не нашлось билетов {origin}", "flight", 3.0))
            elif s.flight_min / 60 > q.max_flight_hours:
                reason = f"перелёт около {_hours(s.flight_min):g} ч, нужно до {q.max_flight_hours:g} ч"
                misses.append(Miss(reason, "flight", (s.flight_min / 60 - q.max_flight_hours) / 2))
        if q.direct_only and not s.direct:
            misses.append(Miss(f"нет прямых рейсов {origin}", "direct", 1.0))
        cap = current_currency.get().to_rub(q.max_ticket) if q.max_ticket else None
        if cap is not None and s.ticket_rub is not None and s.ticket_rub > cap:
            reason = f"билет от {money(s.ticket_rub)}, нужно до {money(cap)}"
            misses.append(Miss(reason, "ticket", (s.ticket_rub - cap) / cap * 2))

    allowed = {"no_visa": NO_VISA, "easy": EASY_VISA}.get(q.visa)
    if allowed is not None and s.visa_rule not in allowed:
        misses.append(Miss(VISA_LABELS.get(s.visa_rule, s.visa_rule), "visa", 1.0))
    if q.with_kids and place.kids == "poor":
        misses.append(Miss(KIDS_LABELS["poor"], "kids", 1.5))
    if q.max_price_level is not None and place.price_level > q.max_price_level:
        reason = f"{PRICE_LABELS[place.price_level]} (цены {place.price_level} из 3)"
        misses.append(Miss(reason, "price", float(place.price_level - q.max_price_level)))
    return [m for m in misses if m is not None]


def near_misses(checked: list[tuple[Snapshot, list[Miss]]], q: SearchQuery) -> list[dict]:
    """Places that miss exactly one constraint: the closest miss of each kind first, so the agent can
    explain the trade-offs («теплее, но дорого», «море тёплое, но лететь 9 часов»), then the next closest."""
    single = sorted(
        ((s, why[0]) for s, why in checked if len(why) == 1 and why[0].gap < MAX_NEAR_GAP),
        key=lambda pair: (pair[1].gap, _rank(pair[0], q)),
    )
    picked, kinds = [], set()
    for s, miss in single:
        if miss.kind not in kinds:
            picked.append((s, miss))
            kinds.add(miss.kind)
    picked += [pair for pair in single if pair not in picked]
    return [
        {"id": s.place.id, "name": s.place.name, "why_not": m.reason} for s, m in picked[:MAX_NEAR_MISSES]
    ]


SWIM_WARM_C = 24
SWIM_OK_C = 21


def _sea_bucket(sea: float | None) -> int:
    """0 warm, 1 swimmable, 2 cold, 3 unknown: for a sea trip this matters more than the flight."""
    if sea is None:
        return 3
    return 0 if sea >= SWIM_WARM_C else 1 if sea >= SWIM_OK_C else 2


def _rank(s: Snapshot, q: SearchQuery) -> tuple:
    travel = s.train_min if q.without_flight else s.flight_min
    sea = s.climate.get(q.month, {}).get("sea_temp") if q.month else None
    sea_trip = q.month is not None and (
        q.min_sea_temp is not None or (q.kinds is not None and "sea" in q.kinds)
    )
    return (
        _sea_bucket(sea) if sea_trip else 0,
        travel if travel is not None else 10_000,
        s.place.price_level,
        -(sea or 0),
    )


def visa_text(s: Snapshot) -> str:
    if s.visa:
        text = visa_sentence(s.visa)
        if fee := fees().known(s.visa):
            text += f" Сбор {fee.for_model()}."
    else:
        text = VISA_LABELS.get(s.visa_rule, s.visa_rule)
        if s.visa_days:
            text += f", до {s.visa_days:.0f} дней"
    return f"{text} {s.visa_note}" if s.visa_note else text


def visa_info(s: Snapshot) -> dict | None:
    """The chip on a card: the rule for the traveller's passport, and its fee when already known."""
    if s.visa is None:
        return None
    fee = fees().known(s.visa)
    return {**visa_view(s.visa), "fee": fee.view() if fee else None}


def _climate_view(values: dict[str, float]) -> dict:
    view = {
        "днём": values.get("air_max"),
        "ночью": values.get("air_min"),
        "море": values.get("sea_temp"),
        "дождливых_дней": values.get("rain_days"),
    }
    return {k: round(v) if k != "дождливых_дней" else round(v, 1) for k, v in view.items() if v is not None}


def sea_trip(q: SearchQuery | None) -> bool:
    """The user asked for the sea: a sea kind or a sea temperature."""
    return bool(q) and (q.min_sea_temp is not None or bool(q.kinds and "sea" in q.kinds))


def sea_matters(s: Snapshot, asked: bool) -> bool:
    """The sea is worth a word: the trip is about it, or the place is a beach place (its first kind). New York
    in May has a sea of 15 °C, and nobody flying there for the city needs to hear it."""
    return asked or (bool(s.place.kinds) and s.place.kinds[0] == "sea")


def describe(s: Snapshot, month: int | None = None, sea: bool | None = None) -> dict:
    place = s.place
    sea = sea_matters(s, False) if sea is None else sea
    result = {
        "id": place.id,
        "name": place.name,
        "country": place.country.name,
        "kinds": [KIND_LABELS[k] for k in place.kinds if sea or k != "sea"],
        "flight_hours": _hours(s.flight_min),
        "direct_flight": s.direct,
        "flight": s.flights.view() if s.flights else None,
        "train_hours": _hours(s.train_min),
        "airport": place.airport,
        "visa": visa_text(s),
        "price": PRICE_LABELS[place.price_level],
        "kids": KIDS_LABELS[place.kids],
        "highlights": list(place.highlights),
        "watch_out": list(place.watch_out),
    }
    if month and month in s.climate:
        climate = _climate_view(s.climate[month])
        if not sea:
            climate.pop("море", None)
        result["climate"] = {"month": MONTHS[month - 1], **climate}
    if s.flags:
        result["data_flags"] = s.flags
    if not s.flights and s.via:
        result["flight_via"] = {k: s.via[k] for k in ("via", "price", "estimate")}
    if not s.flights and s.search_link:
        result["no_cached_ticket"] = "Aviasales has no cached price: the card links to its live search"
    return {k: v for k, v in result.items() if v is not None}


def _card_climate(values: dict[str, float], month: int) -> dict:
    view = {
        "day": values.get("air_max"),
        "night": values.get("air_min"),
        "sea": values.get("sea_temp"),
        "rain_days": values.get("rain_days"),
    }
    rounded = {k: round(v) if k != "rain_days" else round(v, 1) for k, v in view.items() if v is not None}
    return {"month": MONTHS[month - 1], "month_in": MONTHS_IN[month - 1], **rounded}


def card(s: Snapshot, month: int | None = None, sea: bool | None = None) -> dict:
    """One destination as the chat draws it: the facts as numbers, so the UI can lay them out. The sea's
    temperature only where it matters (see sea_matters)."""
    place, climate = s.place, s.climate.get(month) if month else None
    if climate and not (sea_matters(s, False) if sea is None else sea):
        climate = {k: v for k, v in climate.items() if k != "sea_temp"}
    return {
        "id": place.id,
        "name": place.name,
        "country": place.country.name,
        "country_code": place.country.code,
        "lat": place.lat,  # for the map above the cards
        "lon": place.lon,
        "kinds": list(place.kinds),
        "flight_hours": _hours(s.flight_min),
        "direct": s.direct,
        "flight": s.flights.view() if s.flights else None,
        "train_hours": _hours(s.train_min),
        "visa": visa_label(s.visa) if s.visa else VISA_LABELS.get(s.visa_rule, s.visa_rule),
        "visa_easy": s.visa_rule in EASY_VISA,
        "visa_info": visa_info(s),
        # the team's estimates: a route-map city has none, so its card shows none rather than a default
        "price_level": place.price_level if place.verified else None,
        "price": PRICE_LABELS[place.price_level] if place.verified else None,
        "kids": KIDS_LABELS[place.kids] if place.verified else None,
        "kids_fit": place.kids if place.verified else None,
        "climate": _card_climate(climate, month) if climate else None,
        "highlights": list(place.highlights),
        "watch_out": list(place.watch_out),
        "photo": place_photo(place.id),
        "search_link": s.search_link if not s.flights else None,
        "flight_via": s.via if not s.flights else None,
    }


def mixed(matches: list[Snapshot], limit: int, rank) -> list[Snapshot]:
    """The best matches, but with up to half the places from the route map when it has matches: the
    catalogue's nearby resorts would otherwise fill every slot and the wider world would never show."""
    extra = [s for s in matches if not s.place.verified]
    share = min(len(extra), (limit + 1) // 2)
    picked = [s for s in matches if s.place.verified][: limit - share] + extra[:share]
    picked += [s for s in matches if s not in picked][: limit - len(picked)]
    return sorted(picked, key=rank)


def search(snapshots: list[Snapshot], q: SearchQuery, origin: City | None = None) -> dict:
    origin_text = origin.from_text if origin else "из вашего города"
    candidates = [s for s in snapshots if in_scope(s, q)]
    checked = [(s, failures(s, q, origin_text)) for s in candidates]
    matches = sorted((s for s, why in checked if not why), key=lambda s: _rank(s, q))
    shown = mixed(matches, q.limit, lambda s: _rank(s, q))
    return {
        "from": origin.name if origin else None,
        "month": MONTHS[q.month - 1] if q.month else None,
        "matches": [describe(s, q.month, sea_matters(s, sea_trip(q))) for s in shown],
        "more_matches": max(0, len(matches) - q.limit),
        "near_misses": near_misses(checked, q),
        "checked": len(candidates),
        "sources": SOURCES_NOTE,
        **_missing(q),
    }


def _missing(q: SearchQuery) -> dict:
    """What the user hasn't told us yet that changes the pick. The tool says it, so the model asks."""
    missing = []
    if q.with_kids and not q.kids_ages:
        missing.append("возраст детей (от него зависят отели, перелёт и пляж)")
    if q.month is None:
        missing.append("когда ехать")
    if not missing:
        return {}
    return {
        "missing": missing,
        "ask": f"Закончи ответ одним вопросом про {missing[0].split(' (')[0]}.",
    }


def destination_details(s: Snapshot) -> dict:
    details = describe(s)
    details["by_month"] = [{"month": MONTHS[m - 1], **_climate_view(v)} for m, v in sorted(s.climate.items())]
    details["coordinates"] = [s.place.lat, s.place.lon]
    details["wikidata"] = f"https://www.wikidata.org/wiki/{s.place.qid}"
    details["sources"] = SOURCES_NOTE
    return details
