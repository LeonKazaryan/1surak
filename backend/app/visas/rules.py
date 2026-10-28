"""What a passport needs to enter a country, for every pair of the world's countries.

The rules are the Passport Index dataset (MIT, seed built by scripts/build_visa_seed.py). The passport is the
one of the departure city's country: we assume someone flying from Astana holds a Kazakh passport, from Moscow
a Russian one. The names and their cases («граждан Казахстана», «в США») come from Travelpayouts' country list.
"""

import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from app.flights import city, current_origin

SEED = Path(__file__).parent / "seed"
DEFAULT_PASSPORT = "RU"  # the departure city's country unknown: the app's fallback city is Moscow
# The seed's short statuses as the catalogue's visa rules (app.catalog.catalog.VISA_LABELS)
STATUSES = {
    "vf": "visa_free",
    "voa": "on_arrival",
    "eta": "eta",
    "ev": "evisa",
    "vr": "visa_required",
    "na": "no_admission",
}
PAID = {"on_arrival", "eta", "evisa", "visa_required"}  # a fee worth looking up


@dataclass(frozen=True)
class VisaRule:
    passport: str  # ISO 3166-1 alpha-2
    destination: str
    code: str  # none | visa_free | on_arrival | eta | evisa | visa_required | no_admission
    days: int | None = None  # how long the stay may be, where the rule says

    @property
    def paid(self) -> bool:
        return self.code in PAID

    @property
    def key(self) -> str:
        """«KZ-US»: the pair a fee is looked up and cached for."""
        return f"{self.passport}-{self.destination}"


@cache
def _rules() -> dict[str, dict[str, str]]:
    return json.loads((SEED / "passport_index.json").read_text(encoding="utf-8"))


@cache
def _countries() -> dict[str, dict]:
    return json.loads((SEED / "countries.json").read_text(encoding="utf-8"))


def passport_of(origin_code: str | None) -> str:
    """The passport we assume: the country of the departure city."""
    found = city(origin_code) if origin_code else None
    return found.country_code if found and found.country_code else DEFAULT_PASSPORT


def current_passport() -> str:
    """The passport for the request being answered (its departure city is in current_origin)."""
    return passport_of(current_origin.get())


def rule_for(destination: str | None, passport: str | None = None) -> VisaRule | None:
    """The rule for this passport (the current traveller's by default); None for a pair the dataset lacks."""
    if not destination:
        return None
    passport, destination = (passport or current_passport()).upper(), destination.upper()
    if passport == destination:
        return VisaRule(passport, destination, "none")
    raw = _rules().get(passport, {}).get(destination)
    if raw is None:
        return None
    status, _, days = raw.partition(":")
    return VisaRule(passport, destination, STATUSES[status], int(days) if days else None)


def country(code: str, case: str = "su") -> str:
    """A country's name in a case: su «Казахстан», ro «Казахстана», vi «в Казахстан», en «Kazakhstan»."""
    entry = _countries().get(code.upper()) or {}
    if case == "en":
        return entry.get("en") or code
    return (entry.get("cases") or {}).get(case) or entry.get("name") or code


def _days(n: int) -> str:
    tail = n % 100
    word = "дней" if 11 <= tail <= 14 else "день" if n % 10 == 1 else "дня" if 2 <= n % 10 <= 4 else "дней"
    return f"{n} {word}"


def label(rule: VisaRule) -> str:
    """The short text of the card's chip: «без визы до 30 дней», «нужна виза»."""
    if rule.code == "visa_free":
        return f"без визы до {_days(rule.days)}" if rule.days else "без визы"
    return {
        "none": "внутренняя поездка",
        "on_arrival": "виза по прилёте",
        "eta": "электронное разрешение",
        "evisa": "электронная виза",
        "visa_required": "нужна виза",
        "no_admission": "въезд закрыт",
    }[rule.code]


def sentence(rule: VisaRule) -> str:
    """What the chip's hint says: «Для граждан Казахстана нужна виза в США, …»."""
    if rule.code == "none":
        return "Поездка внутри страны, виза не нужна."
    citizens, into = f"Для граждан {country(rule.passport, 'ro')}", country(rule.destination, "vi")
    stay = f", можно остаться до {_days(rule.days)}" if rule.days else ""
    return {
        "visa_free": f"{citizens} виза {into} не нужна{stay}.",
        "on_arrival": f"{citizens} виза {into} ставится по прилёте{stay}.",
        "eta": f"{citizens} нужно электронное разрешение на въезд {into}, его оформляют онлайн заранее.",
        "evisa": f"{citizens} нужна электронная виза {into}, её оформляют онлайн заранее{stay}.",
        "visa_required": f"{citizens} нужна виза {into}, её оформляют заранее в консульстве или визовом центре.",
        "no_admission": f"{citizens} въезд {into} сейчас закрыт.",
    }[rule.code]


@cache
def _areas() -> dict[str, dict]:
    """Groups of countries one visa opens together (scripts/build_visa_areas_seed.py, Wikidata): Schengen."""
    areas = json.loads((SEED / "areas.json").read_text(encoding="utf-8"))
    return {key: {**area, "key": key} for key, area in areas.items()}


@cache
def _accepted() -> dict[str, dict[str, dict]]:
    """Area > the countries outside it that let in a holder of its visa, with the days and the source
    (scripts/build_visa_accepts_seed.py: looked up on the web, kept with the quote)."""
    path = SEED / "areas_accepted.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def area_of(destination: str | None) -> dict | None:
    """The visa area the country is in: {"key": "schengen", "name": "Шенген", "visa": "шенгенская виза", …}."""
    code = (destination or "").upper()
    return next((area for area in _areas().values() if code in area["members"]), None)


def accepts(destination: str, area: dict) -> dict | None:
    """How a country outside the area takes its visa instead of its own: {"days": 30, "multiple_entry": …}."""
    return _accepted().get(area["key"], {}).get(destination.upper())


def _listed(names: list[str]) -> str:
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} и {names[-1]}"


def _into(code: str) -> str:
    """«Италию»: the country after «одна на», from its «в Италию» (an island's is «на Мальту»)."""
    into = country(code, "vi")
    return next((into[len(p) :] for p in ("во ", "в ", "на ") if into.startswith(p)), into)


def _comes_back(order: list[str], area: dict) -> bool:
    """The route leaves the area and enters it again (Greece → Montenegro → Italy): a one-entry visa would not
    let the traveller back in."""
    inside = [code in area["members"] for code in order]
    first = inside.index(True) if True in inside else len(inside)
    last = len(inside) - 1 - inside[::-1].index(True) if True in inside else -1
    return any(not x for x in inside[first:last])


def shared(stays: list[tuple[VisaRule, int]]) -> list[tuple[VisaRule, dict]]:
    """The visas of a route, one chip per visa to get: Italy, Spain and Portugal are one Schengen visa, not three,
    and Montenegro, which lets a Schengen visa in, needs none of its own beside it. `stays` are the rule and the
    nights of each stop in order. Each chip is (the rule its fee is looked up for, its view with the `name`
    before its label). A shared visa is applied for where most nights are spent, or where the trip enters first
    when they are even: the Schengen rule for the main destination."""
    nights: dict[str, int] = {}
    rules: dict[str, VisaRule] = {}
    for rule, n in stays:
        if rule.code not in ("none", "visa_free"):
            nights[rule.destination] = nights.get(rule.destination, 0) + n
            rules.setdefault(rule.destination, rule)
    # the areas whose visa the traveller gets anyway: a member of them on the route needs it
    needed = {a["key"]: a for c, r in rules.items() if r.code == "visa_required" and (a := area_of(c))}
    groups: dict[tuple, list[str]] = {}
    for code, rule in rules.items():  # in the order the route enters them
        area = area_of(code) if rule.code == "visa_required" else None
        if area is None and rule.code == "visa_required":
            area = next((a for a in needed.values() if accepts(code, a)), None)
        groups.setdefault((area["key"], rule.code) if area else (code, rule.code), []).append(code)
    order = [rule.destination for rule, _ in stays]
    chips = []
    for (key, _), codes in groups.items():
        area = needed.get(key)
        if area is None or (len(codes) == 1 and codes[0] in area["members"]):
            rule = rules[codes[0]]  # a visa of its own, or the area's for one member alone
            chips.append((rule, {**view(rule), "name": country(rule.destination)}))
            continue
        chips.append(_area_chip(area, codes, rules, nights, order))
    return chips


def _area_chip(
    area: dict, codes: list[str], rules: dict[str, VisaRule], nights: dict[str, int], order: list[str]
) -> tuple[VisaRule, dict]:
    members = [c for c in codes if c in area["members"]]
    others = [c for c in codes if c not in area["members"]]
    longest = max(nights[c] for c in members)
    main = next(c for c in members if nights[c] == longest)
    unique = sum(nights[c] == longest for c in members) == 1
    rule = rules[main]
    text = f"Для граждан {country(rule.passport, 'ro')} нужна {area['visa']}"
    text += (
        f", одна на {_listed([_into(c) for c in members])}."
        if len(members) > 1
        else f" для {country(main, 'ro')}."
    )
    also, places = [], []
    for code in others:
        taken = accepts(code, area)
        places.append(country(code, "vi") + (f" (до {_days(taken['days'])})" if taken["days"] else ""))
        also.append(
            {"name": country(code), "days": taken["days"], "source": taken["source"], "url": taken["url"]}
        )
    if places:
        text += f" По ней же пускают {_listed(places)}: своя виза туда не нужна."
    back = _comes_back(order, area)
    strict = [country(c) for c in others if accepts(c, area)["multiple_entry"]]
    many = back or bool(strict)
    if back:
        text += " Нужна многократная виза: маршрут выезжает из зоны и возвращается."
    elif strict:
        text += f" Нужна многократная виза: {_listed(strict)} {'пускают' if len(strict) > 1 else 'пускает'} только по ней."
    why = "там больше всего ночей" if unique else "туда первый въезд"
    text += f" Её оформляют заранее в консульстве или визовом центре {country(main, 'ro')}: {why}."
    view_ = {
        **view(rule),
        "name": area["name"],
        "label": "нужна многократная виза" if many else label(rule),
        "text": text,
        "countries": [country(c) for c in members],
        "also": also,
    }
    return rule, view_


def view(rule: VisaRule) -> dict:
    """The visa as a card draws it; the fee comes separately (app.visas.fees)."""
    return {
        "rule": rule.code,
        "label": label(rule),
        "text": sentence(rule),
        "days": rule.days,
        "pair": rule.key,
    }
