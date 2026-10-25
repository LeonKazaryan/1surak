"""What we know about the trip so far, and which of the must-know answers are still missing.

The model fills the brief from the user's words; the code alone decides what is missing, so the agent
asks only what blocks the search, and only once. After that it goes on with stated assumptions.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app.catalog.catalog import KIND_LABELS, Catalog, Kind, load_catalog
from app.catalog.search import MONTHS

Slot = Literal["vibe", "when", "travelers", "route", "budget"]
SLOTS: tuple[Slot, ...] = ("vibe", "when", "travelers", "route", "budget")
MIN_ROUTE_NIGHTS = 5  # shorter trips stay in one place: moving eats the days

# A region the user names, as the catalogue's countries, so «по Кавказу» filters the search right away.
REGION_COUNTRIES = {
    "кавказ": ["Грузия", "Армения", "Азербайджан"],
    "закавказье": ["Грузия", "Армения", "Азербайджан"],
    "европа": ["Сербия", "Черногория", "Беларусь", "Турция"],
    "балканы": ["Сербия", "Черногория"],
    "средняя азия": ["Узбекистан", "Казахстан", "Киргизия"],
    "центральная азия": ["Узбекистан", "Казахстан", "Киргизия"],
    "юго-восточная азия": ["Таиланд", "Вьетнам", "Индонезия"],
    "азия": ["Таиланд", "Вьетнам", "Индонезия", "Китай", "Шри-Ланка", "Индия"],
    "ближний восток": ["ОАЭ", "Оман"],
    "африка": ["Египет", "Тунис", "Танзания", "Сейшельские Острова", "Маврикий"],
}
BUDGET_LABELS = {0: "Бюджет не важен", 1: "Экономно", 2: "Средний бюджет", 3: "Комфорт"}
# Team estimates for a week per person, to turn a sum of money into the catalogue's price level.
LEVEL_CAPS_PER_PERSON = ((70_000, 1), (150_000, 2))


class BriefPatch(BaseModel):
    """What the user stated. None means «not said», so a patch never erases what was known."""

    destination: str | None = Field(
        None, max_length=80, description="Place or country the user named, nominative case: 'Турция'."
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
    budget_total_rub: int | None = Field(None, gt=0, description="Budget for the whole trip and party, RUB.")
    multi_city: bool | None = Field(
        None,
        description="True when the user wants several cities in one trip: 'по Европе', 'Ереван и Тбилиси', "
        "'несколько городов', 'маршрут'. False when they want to stay in one place.",
    )
    wishes: list[str] | None = Field(
        None,
        max_length=10,
        description="Only wishes the fields above cannot hold, in the user's words: 'без долгих перелётов', "
        "'всё включено', 'с собакой'. Never repeat budget ('недорого'), party ('с ребёнком'), "
        "kind of trip ('тёплое море'), dates or the departure city.",
    )


class TripBrief(BriefPatch):
    asked: bool = False  # the clarifying cards were shown, so we never ask twice
    shown: list[str] = Field(default_factory=list)  # destination ids on the last cards


def merge(brief: TripBrief, patch: BriefPatch) -> TripBrief:
    updates = patch.model_dump(exclude_none=True)
    if "wishes" in updates:
        updates["wishes"] = list(dict.fromkeys([*(brief.wishes or []), *updates["wishes"]]))
    if "children_ages" in updates and "children" not in updates:
        updates["children"] = max(brief.children or 0, len(updates["children_ages"]))
    if updates.get("children") == 0:
        updates["children_ages"] = []
    if "date_from" in updates and "month" not in updates:
        updates["month"] = updates["date_from"].month
    return brief.model_copy(update=updates)


def _nights(b: BriefPatch) -> tuple[int | None, int | None]:
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
    _, high = _nights(b)
    if high is not None and high < MIN_ROUTE_NIGHTS:
        return False
    if b.kinds and set(b.kinds) <= {"ski"}:
        return False
    return not (b.destination and load_catalog().find(b.destination))


def missing(b: TripBrief) -> list[Slot]:
    result: list[Slot] = []
    if not b.destination and not b.kinds:
        result.append("vibe")
    if not (b.month or b.date_from) or _nights(b) == (None, None):
        result.append("when")
    if b.adults is None or len(b.children_ages or []) < (b.children or 0):
        result.append("travelers")
    if b.budget_level is None and b.budget_total_rub is None:
        result.append("budget")
    # Rides along with other questions only: a request that says everything still gets zero questions.
    if result and route_fits(b):
        result.insert(len([s for s in result if SLOTS.index(s) < SLOTS.index("route")]), "route")
    return result


def assumptions(b: TripBrief) -> list[str]:
    """What the agent goes on with after the one round of questions, said out loud to the user."""
    gaps = set(missing(b))
    result = []
    if "vibe" in gaps:
        result.append("тип отдыха любой")
    if "when" in gaps:
        if not (b.month or b.date_from):
            result.append("месяц не выбран, поэтому погоду не учитываю")
        if _nights(b) == (None, None):
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
    return result


def price_level(b: TripBrief) -> int | None:
    if b.budget_level:
        return b.budget_level
    if b.budget_total_rub:
        per_person = b.budget_total_rub / max(1, (b.adults or 2) + (b.children or 0))
        return next((level for cap, level in LEVEL_CAPS_PER_PERSON if per_person <= cap), 3)
    return None


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
        countries = [c.name for c in catalog.countries.values() if c.name.casefold() == needle]
        region = next((names for key, names in REGION_COUNTRIES.items() if key in needle), None)
        if countries or region:
            hint["countries"] = countries or region
    if b.multi_city:
        hint["multi_city"] = True  # search_routes, not search_destinations
        _, nights = _nights(b)
        if nights:
            hint["nights"] = nights
    return hint


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
    low, high = _nights(b)
    if low:
        span = f"{low}–{high}" if high != low else f"{low}"
        when.append(f"{span} {plural(high or low, ('ночь', 'ночи', 'ночей'))}")
    if when:
        result.append(" · ".join(when))
    if travelers := _travelers(b):
        result.append(travelers)
    if b.budget_total_rub:
        result.append(f"до {b.budget_total_rub:,} ₽".replace(",", " "))
    elif b.budget_level is not None:
        result.append(BUDGET_LABELS[b.budget_level])
    if b.multi_city:
        result.append("Несколько городов")
    result.extend(b.wishes or [])
    return result


def prefill(b: TripBrief) -> dict:
    """What the question cards start from, so the user only confirms what we already understood."""
    low, high = _nights(b)
    return {
        "kinds": list(b.kinds or []),
        "month": b.month,
        "nights": [low, high] if low else None,
        "adults": b.adults,
        "children": b.children,
        "children_ages": list(b.children_ages or []),
        "budget_level": b.budget_level,
        "multi_city": b.multi_city,
    }
