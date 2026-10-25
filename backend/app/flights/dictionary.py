"""Travelpayouts dictionaries, committed as seed (scripts/build_flights_seed.py): cities with an airport, airlines."""

import json
import math
from dataclasses import dataclass
from functools import cache
from pathlib import Path

SEED = Path(__file__).parent / "seed"
LOGO_URL = "https://pics.avs.io/{size}/{size}/{code}.png"  # Aviasales' airline logo CDN


@dataclass(frozen=True)
class City:
    code: str
    name: str
    country: str
    lat: float
    lon: float
    name_from: str | None = None  # «Астаны», for «из Астаны»

    @property
    def from_text(self) -> str:
        return f"из {self.name_from or self.name}"

    def view(self) -> dict:
        return {
            "code": self.code,
            "name": self.name,
            "country": self.country,
            "lat": self.lat,
            "lon": self.lon,
        }


@cache
def cities() -> dict[str, City]:
    rows = json.loads((SEED / "cities.json").read_text(encoding="utf-8"))
    return {
        r["code"]: City(r["code"], r["name"], r["country"], r["lat"], r["lon"], r.get("from")) for r in rows
    }


@cache
def airlines() -> dict[str, str]:
    return json.loads((SEED / "airlines.json").read_text(encoding="utf-8"))


def city(code: str | None) -> City | None:
    return cities().get((code or "").upper())


def airline_name(code: str) -> str:
    return airlines().get(code, code)


def rub(value: int) -> str:
    """10558 → «10 558 ₽»."""
    return f"{value:,} ₽".replace(",", "\u00a0")


def logo_url(code: str, size: int = 64) -> str:
    return LOGO_URL.format(size=size, code=code)


def _distance(city: City, lat: float, lon: float) -> float:
    x = math.radians(lon - city.lon) * math.cos(math.radians((lat + city.lat) / 2))
    return math.hypot(x, math.radians(lat - city.lat))


def nearest(lat: float, lon: float, limit: int = 8) -> list[City]:
    return sorted(cities().values(), key=lambda c: _distance(c, lat, lon))[:limit]
