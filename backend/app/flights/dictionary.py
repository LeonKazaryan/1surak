"""Travelpayouts dictionaries, committed as seed (scripts/build_flights_seed.py): cities with an airport, airlines.

Every code is read as a city: an airport code (SVO, PEK) means its city (MOW, BJS), so one city is one node.
"""

import json
import math
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from zoneinfo import ZoneInfo

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
    country_code: str | None = None
    tz: str | None = None
    airport: tuple[float, float] | None = None  # the main airport, for the ride to the hotel
    name_in: str | None = None  # «Ташкенте», for «в Ташкенте»

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
        r["code"]: City(
            r["code"],
            r["name"],
            r["country"],
            r["lat"],
            r["lon"],
            r.get("from"),
            r.get("cc"),
            r.get("tz"),
            tuple(r["air"]) if r.get("air") else None,
            r.get("in"),
        )
        for r in rows
    }


@cache
def _zones() -> dict[str, str]:
    """City code > IANA time zone, from the same Travelpayouts city list: {"TAS": "Asia/Tashkent"}."""
    return json.loads((SEED / "timezones.json").read_text(encoding="utf-8"))


def time_zone(place: City) -> ZoneInfo | None:
    """The city's local time: a train after a flight leaves by the clock of the city the plane landed in."""
    name = _zones().get(place.code)
    return ZoneInfo(name) if name else None


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


def _key(name: str) -> str:
    return name.strip().casefold().replace("ё", "е")


@cache
def _reach() -> dict[str, int]:
    """How many cities each city has a direct flight to, from the route map."""
    routes = json.loads((SEED / "routes.json").read_text(encoding="utf-8"))
    return {code: len(destinations) for code, destinations in routes.items()}


@cache
def _by_name() -> dict[str, City]:
    """A name of several cities is the best connected one: «Лондон» is London with 324 routes, not London,
    Ontario with two; «Барселона» is in Spain, not in Venezuela."""
    found: dict[str, City] = {}
    reach = _reach()
    for c in sorted(cities().values(), key=lambda c: -reach.get(c.code, 0)):
        for name in (c.name, c.name_from):
            if name:
                found.setdefault(_key(name), c)
    return found


def find_city(name: str | None) -> City | None:
    """A city by IATA code (city or airport) or by its Russian name: 'NQZ', 'svo', 'Астана', 'астаны'."""
    if not name or not name.strip():
        return None
    return city(name) or _by_name().get(_key(name))


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
