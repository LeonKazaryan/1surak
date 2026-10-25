"""Real sights, food spots, local dishes and photos per place, adapted from Wikivoyage and Commons.

Built once by scripts/build_guide_seed.py into seed/guide.json (CC BY-SA, see seed/NOTICE.md).
"""

import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path

GUIDE_PATH = Path(__file__).parent / "seed" / "guide.json"
FOOD_TYPES = {"eat", "drink"}


@dataclass(frozen=True)
class Photo:
    url: str
    width: int
    height: int
    author: str
    license: str
    file_url: str

    def view(self) -> dict:
        return {
            "url": self.url,
            "width": self.width,
            "height": self.height,
            "author": self.author,
            "license": self.license,
            "file_url": self.file_url,
        }


@dataclass(frozen=True)
class Spot:
    id: str
    type: str  # see | do | vicinity | eat | drink
    name: str
    summary: str
    lat: float | None = None
    lon: float | None = None
    star: bool = False
    hours: str | None = None
    price: str | None = None
    photo: Photo | None = None
    alt: str | None = None
    source_url: str | None = None

    def view(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "alt": self.alt,
            "summary": self.summary,
            "hours": self.hours,
            "price": self.price,
            "photo": self.photo.view() if self.photo else None,
            "lat": self.lat,
            "lon": self.lon,
            "source_url": self.source_url,
        }


@dataclass(frozen=True)
class Dish:
    name: str
    note: str


@dataclass(frozen=True)
class Guide:
    place_id: str
    sights: tuple[Spot, ...] = ()
    food: tuple[Spot, ...] = ()
    dishes: tuple[Dish, ...] = ()
    food_intro: str | None = None
    photo: Photo | None = None
    source_url: str | None = None


def _photo(raw: dict | None) -> Photo | None:
    if not raw:
        return None
    return Photo(raw["url"], raw["width"], raw["height"], raw["author"], raw["license"], raw["file_url"])


def _spot(raw: dict) -> Spot:
    return Spot(
        id=raw["id"],
        type=raw["type"],
        name=raw["name"],
        summary=raw["summary"],
        lat=raw.get("lat"),
        lon=raw.get("lon"),
        star=bool(raw.get("star")),
        hours=raw.get("hours"),
        price=raw.get("price"),
        photo=_photo(raw.get("photo")),
        alt=raw.get("alt"),
        source_url=raw.get("source_url"),
    )


def parse_guide(place_id: str, raw: dict) -> Guide:
    spots = [_spot(item) for item in raw.get("listings", [])]
    return Guide(
        place_id=place_id,
        sights=tuple(s for s in spots if s.type not in FOOD_TYPES),
        food=tuple(s for s in spots if s.type in FOOD_TYPES),
        dishes=tuple(Dish(d["name"], d.get("note") or "") for d in raw.get("dishes", [])),
        food_intro=raw.get("food_intro"),
        photo=_photo(raw.get("photo")),
        source_url=raw.get("source_url"),
    )


@cache
def _seed() -> dict:
    if not GUIDE_PATH.exists():
        return {}
    return json.loads(GUIDE_PATH.read_text(encoding="utf-8"))["places"]


def guide_for(place_id: str) -> Guide:
    raw = _seed().get(place_id)
    return parse_guide(place_id, raw) if raw else Guide(place_id)


def place_photo(place_id: str) -> dict | None:
    photo = guide_for(place_id).photo
    return photo.view() if photo else None
