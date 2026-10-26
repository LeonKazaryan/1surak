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


def view(rule: VisaRule) -> dict:
    """The visa as a card draws it; the fee comes separately (app.visas.fees)."""
    return {
        "rule": rule.code,
        "label": label(rule),
        "text": sentence(rule),
        "days": rule.days,
        "pair": rule.key,
    }
