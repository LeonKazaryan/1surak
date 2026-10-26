"""The hotel directory: real hotels around each catalogue place, built by scripts/build_hotels_seed.py.

Only what the sources say: the name, where it is, the stars when OpenStreetMap has them, a Commons photo for
the notable ones. Nothing about rooms, meals, ratings or kids clubs: we do not know those, so we never claim
them. Prices are offers (offers.py), estimated until a real provider is plugged in.
"""

import json
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

SEED = Path(__file__).parent / "seed" / "hotels.json"
WIKIDATA_URL = "https://www.wikidata.org/wiki/{}"
OSM_URL = "https://www.openstreetmap.org/{}"


@dataclass(frozen=True)
class Listed:
    id: str  # «kazan-hq123», «kazan-how456»: the place id first, as the plan expects
    place_id: str
    name: str
    stars: int | None
    lat: float
    lon: float
    centre_m: int  # from the place's centre, in a straight line
    photo: dict | None  # a Commons photo with its author and licence, as the guide keeps them
    source_url: str
    website: str | None = None
    tags: dict[str, str] = field(
        default_factory=dict, hash=False, compare=False
    )  # OSM amenities: dog, internet


def hotel_id(place_id: str, row: dict) -> str:
    if row.get("osm"):
        kind, number = row["osm"].split("/")
        return f"{place_id}-ho{kind[0]}{number}"
    return f"{place_id}-hq{row['qid'].removeprefix('Q')}"


def _listed(place_id: str, row: dict) -> Listed:
    source = OSM_URL.format(row["osm"]) if row.get("osm") else WIKIDATA_URL.format(row["qid"])
    return Listed(
        id=hotel_id(place_id, row),
        place_id=place_id,
        name=row["name"],
        stars=row.get("stars"),
        lat=row["lat"],
        lon=row["lon"],
        centre_m=row.get("centre_m", 0),
        photo=row.get("photo"),
        source_url=source,
        website=row.get("website"),
    )


@cache
def directory() -> dict[str, tuple[Listed, ...]]:
    if not SEED.exists():
        return {}
    places = json.loads(SEED.read_text(encoding="utf-8"))["places"]
    return {pid: tuple(_listed(pid, row) for row in rows) for pid, rows in places.items()}


def listed(place_id: str) -> tuple[Listed, ...]:
    return directory().get(place_id, ())


def find(hotel_id_: str) -> Listed | None:
    place_id = hotel_id_.rsplit("-h", 1)[0]
    return next((h for h in listed(place_id) if h.id == hotel_id_), None)
