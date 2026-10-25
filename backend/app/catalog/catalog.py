"""The destination catalogue: which places we offer, and the curated facts about them.

Identity and descriptive fields (kinds, highlights, risks) live in curated/places.json.
Every number (climate, sea, flight time, visa days) is a fact in the facts table, so it carries its
source and can be overridden by a better source later (see docs/08-data-model.md).
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import cache
from pathlib import Path
from typing import Literal

from app.facts.model import Fact

ROOT = Path(__file__).parent
CURATED_PATH = ROOT / "curated" / "places.json"
GEO_PATH = ROOT / "seed" / "places_geo.json"
SEED_FACTS_PATH = ROOT / "seed" / "facts.json"

ORIGIN = "MOW"
ORIGIN_NAME = "Москва"
CURATED_SOURCE = "1surak-curated"
CURATED_ON = datetime(2026, 10, 25, tzinfo=UTC)

Kind = Literal["sea", "mountains", "city", "nature", "ski"]
VisaRule = Literal["none", "visa_free", "on_arrival", "evisa", "visa_required"]
KidsFit = Literal["good", "ok", "poor"]

KIND_LABELS: dict[str, str] = {
    "sea": "море",
    "mountains": "горы",
    "city": "город",
    "nature": "природа",
    "ski": "горные лыжи",
}
VISA_LABELS: dict[str, str] = {
    "none": "внутренняя поездка",
    "visa_free": "без визы",
    "on_arrival": "виза по прибытии",
    "evisa": "электронная виза заранее",
    "visa_required": "нужна виза заранее",
}
PRICE_LABELS = {1: "недорого", 2: "средне", 3: "дорого"}
KIDS_LABELS = {"good": "хорошо с детьми", "ok": "можно с детьми", "poor": "не для маленьких детей"}


@dataclass(frozen=True)
class Country:
    code: str
    name: str
    visa: VisaRule
    visa_days: int | None
    visa_note: str
    name_en: str = ""


@dataclass(frozen=True)
class Place:
    id: str
    qid: str
    name: str
    country: Country
    kinds: tuple[str, ...]
    airport: str | None
    lat: float
    lon: float
    price_level: int
    kids: KidsFit
    highlights: tuple[str, ...]
    watch_out: tuple[str, ...]
    # curated route numbers, turned into facts by curated_facts()
    flight_min: int | None
    direct: bool
    train_min: int | None

    @property
    def domestic(self) -> bool:
        return self.country.code == "RU"

    @property
    def route_id(self) -> str:
        return f"{ORIGIN}>{self.qid}"


@dataclass(frozen=True)
class Catalog:
    places: tuple[Place, ...]
    countries: dict[str, Country]

    def find_country(self, key: str) -> Country | None:
        """By ISO code, Russian or English name; «ОАЭ», «UAE» and «Эмираты» style aliases are not covered."""
        needle = key.strip().casefold()
        for country in self.countries.values():
            if needle in (country.code.casefold(), country.name.casefold(), country.name_en.casefold()):
                return country
        return None

    def find(self, key: str) -> Place | None:
        """By our id, QID or name (case-insensitive), since the model may pass any of them."""
        needle = key.strip().casefold()
        for place in self.places:
            if needle in (place.id, place.qid.casefold(), place.name.casefold()):
                return place
        for place in self.places:
            if needle and needle in place.name.casefold():
                return place
        return None


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def parse_catalog(curated: dict, geo: dict) -> Catalog:
    countries = {
        code: Country(code, c["name"], c["visa"], c["visa_days"], c["visa_note"], c.get("name_en", ""))
        for code, c in curated["countries"].items()
    }
    places = []
    for p in curated["places"]:
        g = geo.get(p["id"])
        if g is None:
            raise ValueError(f"place {p['id']!r} has no QID yet, run scripts/build_catalog_seed.py")
        places.append(
            Place(
                id=p["id"],
                qid=g["qid"],
                name=p["name"],
                country=countries[p["country"]],
                kinds=tuple(p["kinds"]),
                airport=p["airport"],
                lat=g["lat"],
                lon=g["lon"],
                price_level=p["price_level"],
                kids=p["kids"],
                highlights=tuple(p["highlights"]),
                watch_out=tuple(p["watch_out"]),
                flight_min=p["flight_min"],
                direct=p["direct"],
                train_min=p["train_min"],
            )
        )
    return Catalog(places=tuple(places), countries=countries)


@cache
def load_catalog() -> Catalog:
    return parse_catalog(_read(CURATED_PATH), _read(GEO_PATH))


def _curated(entity_type: str, entity_id: str, attribute: str, value, unit: str | None = None) -> Fact:
    return Fact(
        entity_type=entity_type,
        entity_id=entity_id,
        attribute=attribute,
        value=value,
        unit=unit,
        source=CURATED_SOURCE,
        source_tier="community",
        kind="estimated",
        fetched_at=CURATED_ON,
    )


def curated_facts(catalog: Catalog) -> list[Fact]:
    """Our hand-made numbers as facts: tier 'community', kind 'estimated', so any real source wins."""
    result: list[Fact] = []
    for place in catalog.places:
        if place.flight_min is not None:
            result.append(_curated("route", place.route_id, "flight_duration", place.flight_min, "min"))
            result.append(_curated("route", place.route_id, "direct", place.direct))
        if place.train_min is not None:
            result.append(_curated("route", place.route_id, "train_duration", place.train_min, "min"))
    for country in catalog.countries.values():
        result.append(_curated("country", country.code, "visa_rule", country.visa))
        result.append(_curated("country", country.code, "visa_note", country.visa_note))
        if country.visa_days is not None:
            result.append(_curated("country", country.code, "visa_days", country.visa_days, "days"))
    return result


def seed_facts() -> list[Fact]:
    """Facts fetched by the build script (Open-Meteo climate and sea), committed as JSON."""
    rows = _read(SEED_FACTS_PATH)
    return [
        Fact(
            **{
                **row,
                "fetched_at": datetime.fromisoformat(row["fetched_at"]),
                "valid_until": datetime.fromisoformat(row["valid_until"]) if row["valid_until"] else None,
            }
        )
        for row in rows
    ]
