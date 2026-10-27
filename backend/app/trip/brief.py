"""What we know about the trip so far, and which of the must-know answers are still missing.

The model fills the brief from the user's words; the code alone decides what is missing, so the agent
asks only what blocks the search, and only once. After that it goes on with stated assumptions.
"""

import re
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

from app.catalog.catalog import KIND_LABELS, Catalog, Kind, load_catalog
from app.catalog.search import MONTHS
from app.destinations.regions import countries_in, country_names
from app.flights import city, current_origin
from app.flights.dictionary import find_city
from app.money import CURRENCIES, CurrencyCode, current_currency

Slot = Literal["origin", "vibe", "when", "travelers", "route", "budget", "visa"]
SLOTS: tuple[Slot, ...] = ("origin", "vibe", "when", "travelers", "route", "budget", "visa")
MIN_ROUTE_NIGHTS = 5  # shorter trips stay in one place: moving eats the days

BUDGET_LABELS = {0: "Бюджет не важен", 1: "Экономно", 2: "Средний бюджет", 3: "Комфорт"}
# Team estimates for a week per person, to turn a sum of money into the catalogue's price level.
LEVEL_CAPS_PER_PERSON = ((70_000, 1), (150_000, 2))
MAX_WISHES = 10


class BriefPatch(BaseModel):
    """What the user stated. None means «not said», so a patch never erases what was known."""

    destination: str | None = Field(
        None,
        max_length=80,
        description="Place, country or region the user named, nominative case: 'Турция', 'Европа', 'Кавказ' "
        "(«в Европу» = 'Европа'). The search then stays inside it.",
    )
    origin: str | None = Field(
        None,
        max_length=80,
        description="Departure city, only if the user named one ('из Алматы', 'летим из Казани'), "
        "nominative case: 'Алматы'. Flights are then searched from it.",
    )
    kinds: list[Kind] | None = Field(None, description="Kinds of trip the user asked for.")
    month: int | None = Field(None, ge=1, le=12, description="Travel month 1-12.")
    date_from: date | None = None
    date_to: date | None = None
    nights_min: int | None = Field(None, ge=1, le=60)
    nights_max: int | None = Field(None, ge=1, le=60)
    adults: int | None = Field(None, ge=1, le=12)
    children: int | None = Field(None, ge=0, le=10, description="Number of children, 0 if none.")
    children_ages: list[int] | None = Field(None, max_length=10, description="Age of each child, 0-17.")
    budget_level: int | None = Field(
        None, ge=0, le=3, description="0 does not matter, 1 budget, 2 mid-range, 3 comfort."
    )
    budget_total: int | None = Field(
        None,
        gt=0,
        le=10**10,
        description="Budget for the whole trip and party, as the amount the user named. A price per night "
        "('отель до 8000 за ночь') or per ticket is not the trip budget: put it in wishes in the user's words.",
    )
    budget_currency: CurrencyCode | None = Field(
        None,
        description="Currency of budget_total if the user named one ('рублей', '$'); omit for their own.",
    )
    multi_city: bool | None = Field(
        None,
        description="True when the user wants several cities in one trip: 'по Европе', 'Ереван и Тбилиси', "
        "'несколько городов', 'маршрут'. False when they want to stay in one place.",
    )
    by_land: bool | None = Field(
        None,
        description="True when the user wants to go by train or bus, not by plane: 'на поезде', "
        "'без самолётов', 'боюсь летать'.",
    )
    visa_free_only: bool | None = Field(
        None,
        description="True when the user wants no visa hassle ('без визы', 'чтобы без визы'); False when the visa "
        "does not matter to them.",
    )
    wishes: list[Annotated[str, StringConstraints(max_length=80)]] | None = Field(
        None,
        max_length=MAX_WISHES,
        description="Only wishes the fields above cannot hold, in the user's words: 'без долгих перелётов', "
        "'всё включено', 'с собакой'. Never repeat budget ('недорого'), party ('с ребёнком'), "
        "kind of trip ('тёплое море'), dates, the departure city or trains (by_land).",
    )


class TripBrief(BriefPatch):
    asked: bool = False  # the clarifying cards were shown, so we never ask twice
    shown: list[str] = Field(default_factory=list)  # destination ids on the last cards
    priced_from: str | None = None  # IATA of the city the tickets on those cards fly from
    priced_at: datetime | None = None  # when those tickets were found
    plan: dict | None = None  # the last trip plan shown, in short, so the next one can say what changed
    # IATA of the departure city the user named in the chat or picked on a card; it beats the IP guess
    origin_code: str | None = None
    origin_over: str | None = None  # the guess it replaced: the picker still says so until it syncs
    origin_guess: bool = False  # set per turn: the city is the fallback, nobody picked or confirmed it
    currency: str | None = None  # picked by the user on the start screen; None follows the departure city


def merge(brief: TripBrief, patch: BriefPatch) -> TripBrief:
    updates = patch.model_dump(exclude_none=True)
    if "origin" in updates:
        found = find_city(updates["origin"])
        if found:  # an unknown name stays as text: the tool says it found no such city
            if found.code != brief.origin_code:
                updates["origin_over"] = current_origin.get()
            updates["origin_code"] = found.code
            updates["origin"] = found.name
    if "budget_total" in updates and "budget_currency" not in updates:
        updates["budget_currency"] = current_currency.get().code
    if "wishes" in updates:
        updates["wishes"] = list(dict.fromkeys([*(brief.wishes or []), *updates["wishes"]]))[-MAX_WISHES:]
    if "children_ages" in updates and "children" not in updates:
        updates["children"] = max(brief.children or 0, len(updates["children_ages"]))
    if updates.get("children") == 0:
        updates["children_ages"] = []
    if "date_from" in updates and "month" not in updates:
        updates["month"] = updates["date_from"].month
    return brief.model_copy(update=updates)


def night_range(b: BriefPatch) -> tuple[int | None, int | None]:
    if b.nights_min or b.nights_max:
        return b.nights_min or b.nights_max, b.nights_max or b.nights_min
    if b.date_from and b.date_to and b.date_to > b.date_from:
        n = (b.date_to - b.date_from).days
        return n, n
    return None, None


def route_fits(b: TripBrief) -> bool:
    """Whether «one city or several?» is worth asking: not with children (a route is tiring for them),
    not for a short or a ski trip, not when the user named one place."""
    if b.multi_city is not None or b.children:
        return False
    _, high = night_range(b)
    if high is not None and high < MIN_ROUTE_NIGHTS:
        return False
    if b.kinds and set(b.kinds) <= {"ski"}:
        return False
    if b.destination and country_names(b.destination.strip().casefold()):
        return False  # a country: its cards show single cities and routes side by side, nothing to ask
    return not (b.destination and load_catalog().find(b.destination))


def missing(b: TripBrief) -> list[Slot]:
    """What to ask: only what the user has not said yet. What the message already says is never asked again,
    so a request that says everything gets no questions at all."""
    return _gaps(b)


ASK_FIRST = (
    "Ask first: call ask_user. On a new trip the user confirms the brief on the question cards before "
    "anything is searched, built or shown."
)


def cards_first(b: TripBrief) -> dict | None:
    """The refusal a tool gives while the cards of a new trip have not been shown yet."""
    return {"error": ASK_FIRST} if not b.asked and missing(b) else None


PER_NIGHT = re.compile(r"ноч|сутк|night", re.IGNORECASE)


def per_night_budget(patch: "BriefPatch") -> bool:
    """«отель до 8 000 ₽ за ночь» read as the trip budget: the same number sits in a per-night wish."""
    if not patch.budget_total:
        return False
    digits = str(patch.budget_total)
    return any(PER_NIGHT.search(w) and digits in re.sub(r"\D", "", w) for w in patch.wishes or [])


def _open_search(b: TripBrief) -> bool:
    """No destination, or only a region («Европа»): the kind of trip and the visa still choose the places."""
    if not b.destination:
        return True
    needle = b.destination.strip().casefold()
    return country_names(needle) is None and countries_in(needle) is not None


def _gaps(b: TripBrief) -> list[Slot]:
    result: list[Slot] = []
    # every ticket depends on it: asked only when the city is a fallback, never when it was detected
    if b.origin_guess and not b.origin_code:
        result.append("origin")
    if _open_search(b) and not b.kinds:
        result.append("vibe")
    if not (b.month or b.date_from) or night_range(b) == (None, None):
        result.append("when")
    if b.adults is None or len(b.children_ages or []) < (b.children or 0):
        result.append("travelers")
    if b.budget_level is None and b.budget_total is None:
        result.append("budget")
    # Rides along with other questions only: a request that says everything still gets zero questions.
    if any(s != "origin" for s in result) and route_fits(b):
        result.insert(len([s for s in result if SLOTS.index(s) < SLOTS.index("route")]), "route")
    # rides along too, and only for an open search: a place the user named is wanted whatever its visa
    if any(s != "origin" for s in result) and _open_search(b) and b.visa_free_only is None:
        result.append("visa")
    return result


def assumptions(b: TripBrief) -> list[str]:
    """What the agent goes on with after the one round of questions, said out loud to the user."""
    gaps = set(_gaps(b))
    result = []
    if "origin" in gaps and (home := city(current_origin.get())):
        result.append(f"вылет {home.from_text}")
    if "vibe" in gaps:
        result.append("тип отдыха любой")
    if "when" in gaps:
        if not (b.month or b.date_from):
            result.append("месяц не выбран, поэтому погоду не учитываю")
        if night_range(b) == (None, None):
            result.append("7 ночей")
    if "travelers" in gaps:
        if b.adults is None:
            result.append("2 взрослых")
        if len(b.children_ages or []) < (b.children or 0):
            result.append("возраст детей не указан")
    if "budget" in gaps:
        result.append("бюджет не ограничен")
    if "route" in gaps:
        result.append("один город, без переездов")
    if "visa" in gaps:
        result.append("визы не учитываю: места с визой будут с пометкой")
    return result


def price_level(b: TripBrief) -> int | None:
    if b.budget_level:
        return b.budget_level
    if b.budget_total:
        rub = CURRENCIES[b.budget_currency or "RUB"].to_rub(b.budget_total)
        per_person = rub / max(1, (b.adults or 2) + (b.children or 0))
        return next((level for cap, level in LEVEL_CAPS_PER_PERSON if per_person <= cap), 3)
    return None


MAX_NAMED = 7  # cities of one route (app.trip.routes.MAX_STOPS)
STOP_SEPARATORS = re.compile(
    r"\s*(?:,|;|→|->|—|–|\s-\s|\sи\s|\sпотом\s|\sзатем\s|\sа потом\s)\s*", re.IGNORECASE
)


LEADING_WORDS = re.compile(r"^(?:а потом|потом|затем|и|а)\s+", re.IGNORECASE)


def named_stops(destination: str | None, catalog: Catalog) -> list[str]:
    """«Ташкент и Бишкек» > ['Ташкент', 'Бишкек']: two or more places, every one a known city or place."""
    if not destination:
        return []
    parts = [LEADING_WORDS.sub("", part.strip(" .")) for part in STOP_SEPARATORS.split(destination)]
    parts = [part for part in parts if part]
    if len(parts) < 2:
        return []
    names = []
    for part in parts:
        place = next((p for p in catalog.places if p.name.casefold() == part.casefold()), None)
        found = place.name if place else (c.name if (c := find_city(part)) else None)
        if found is None:
            return []
        names.append(found)
    return list(dict.fromkeys(names))


def search_hint(b: TripBrief, catalog: Catalog) -> dict:
    """The filters that follow from the brief alone; the model adds its own reading (warm sea, short flight)."""
    hint: dict = {}
    if b.month:
        hint["month"] = b.month
    if b.kinds:
        hint["kinds"] = list(b.kinds)
    if b.children:
        hint["with_kids"] = True
    if level := price_level(b):
        hint["max_price_level"] = level
    if b.destination:
        needle = b.destination.strip().casefold()
        # any country or region in the world: route-map cities fill what the catalogue lacks
        countries = country_names(needle)
        region = None if countries else countries_in(needle)
        if countries or region:
            hint["countries"] = countries or region
        if countries and b.multi_city is None and _route_length(b):
            hint["also_routes"] = True  # «хочу в Турцию»: one city or a few of them, both on the cards
    if b.kinds and len(b.kinds) >= VARIETY_KINDS and b.multi_city is None and _route_length(b):
        hint["also_routes"] = True  # «всего понемногу»: a route covers several kinds, a single place rarely
    if b.visa_free_only:
        hint["visa"] = (
            "easy"  # no visa or one on arrival; otherwise every place shows, the card says «нужна виза»
        )
    if b.by_land:
        hint["by_land"] = True  # search_routes: trains and buses on every hop where they run
    if stops := named_stops(b.destination, catalog):
        ids = {p.name: p.id for p in catalog.places}
        if len(stops) <= MAX_NAMED and all(name in ids for name in stops):
            # all of them in the catalogue: search_routes builds the route with trains, smarter ways, nights
            hint["route_places"] = [ids[name] for name in stops]
        else:
            hint["plan_route"] = {"stops": stops}  # the user's own cities: priced as they are, not suggested
    elif b.multi_city:
        hint["multi_city"] = True  # search_routes, not search_destinations
        _, nights = night_range(b)
        if nights:
            hint["nights"] = nights
    return hint


VARIETY_KINDS = 3  # this many kinds of trip at once is «всего понемногу»


def _route_length(b: TripBrief) -> bool:
    """Long enough for a few cities and not with children: moving tires them."""
    _, high = night_range(b)
    return not b.children and (high is None or high >= MIN_ROUTE_NIGHTS)


def plural(n: int, forms: tuple[str, str, str]) -> str:
    """Russian plural: (1 ночь, 2 ночи, 5 ночей)."""
    tail = n % 100
    if 11 <= tail <= 14:
        return forms[2]
    return forms[0] if n % 10 == 1 else forms[1] if 2 <= n % 10 <= 4 else forms[2]


def _travelers(b: TripBrief) -> str | None:
    if b.adults is None and not b.children:
        return None
    parts = []
    if b.adults:
        parts.append(f"{b.adults} {plural(b.adults, ('взрослый', 'взрослых', 'взрослых'))}")
    if b.children:
        kids = f"{b.children} {plural(b.children, ('ребёнок', 'ребёнка', 'детей'))}"
        if ages := b.children_ages:
            last = ages[-1]
            listed = ", ".join(str(a) for a in ages[:-1])
            kids += f" ({listed + ' и ' if listed else ''}{last} {plural(last, ('год', 'года', 'лет'))})"
        parts.append(kids)
    return " + ".join(parts)


def chips(b: TripBrief) -> list[str]:
    """The brief in a few short phrases, for the summary row above the destination cards."""
    result = []
    if b.destination:
        result.append(b.destination)
    elif b.kinds:
        result.append(", ".join(KIND_LABELS[k] for k in b.kinds).capitalize())
    when = []
    if b.month:
        when.append(MONTHS[b.month - 1].capitalize())
    low, high = night_range(b)
    if low:
        span = f"{low}–{high}" if high != low else f"{low}"
        when.append(f"{span} {plural(high or low, ('ночь', 'ночи', 'ночей'))}")
    if when:
        result.append(" · ".join(when))
    if travelers := _travelers(b):
        result.append(travelers)
    if b.budget_total:
        result.append(f"до {CURRENCIES[b.budget_currency or 'RUB'].amount(b.budget_total)}")
    elif b.budget_level is not None:
        result.append(BUDGET_LABELS[b.budget_level])
    if b.multi_city:
        result.append("Несколько городов")
    if b.visa_free_only:
        result.append("Без визы")
    if b.origin_code and (home := city(b.origin_code)):
        result.append(home.from_text[:1].upper() + home.from_text[1:])
    result.extend(b.wishes or [])
    return result


def _in_user_currency(b: TripBrief) -> int:
    rub = CURRENCIES[b.budget_currency or "RUB"].to_rub(b.budget_total)
    return current_currency.get().from_rub(rub)


def prefill(b: TripBrief) -> dict:
    """What the question cards start from, so the user only confirms what we already understood."""
    low, high = night_range(b)
    return {
        "kinds": list(b.kinds or []),
        "month": b.month,
        "nights": [low, high] if low else None,
        "adults": b.adults,
        "children": b.children,
        "children_ages": list(b.children_ages or []),
        "budget_level": b.budget_level,
        "visa_free_only": b.visa_free_only,
        # the sum the user named, in their own currency: the cards show it ready to confirm
        "budget_total": _in_user_currency(b) if b.budget_total else None,
        "multi_city": b.multi_city,
        "origin": (home := city(current_origin.get())) and {"code": home.code, "name": home.name},
    }
