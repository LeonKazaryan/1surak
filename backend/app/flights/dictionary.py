"""Travelpayouts dictionaries, committed as seed (scripts/build_flights_seed.py): cities with an airport, airlines.

Every code is read as a city: an airport code (SVO, PEK) means its city (MOW, BJS), so one city is one node.
"""

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


@cache
def airports() -> dict[str, str]:
    """Airport > city code, only where they differ: {"SVO": "MOW", "PEK": "BJS"}."""
    return json.loads((SEED / "airports.json").read_text(encoding="utf-8"))


def city_code(code: str | None) -> str:
    """The city behind an IATA code: "svo" > "MOW", "AYT" > "AYT"; unknown codes come back upper-cased."""
    code = (code or "").strip().upper()
    return airports().get(code, code)


def city(code: str | None) -> City | None:
    return cities().get(city_code(code))


def airline_name(code: str) -> str:
    return airlines().get(code, code)


def logo_url(code: str, size: int = 64) -> str:
    return LOGO_URL.format(size=size, code=code)


EARTH_KM = 6371.0


def distance_km(a: City, b: City) -> float:
    """Great-circle distance."""
    lat1, lat2 = math.radians(a.lat), math.radians(b.lat)
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(math.radians(b.lon - a.lon) / 2) ** 2
    )
    return 2 * EARTH_KM * math.asin(min(1.0, math.sqrt(h)))


def _distance(city: City, lat: float, lon: float) -> float:
    x = math.radians(lon - city.lon) * math.cos(math.radians((lat + city.lat) / 2))
    return math.hypot(x, math.radians(lat - city.lat))


def nearest(lat: float, lon: float, limit: int = 8) -> list[City]:
    return sorted(cities().values(), key=lambda c: _distance(c, lat, lon))[:limit]
