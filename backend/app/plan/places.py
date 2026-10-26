"""What the trip assembly needs about a place beyond the catalogue: its time zone and its airport."""

import json
from dataclasses import dataclass
from datetime import datetime
from functools import cache
from pathlib import Path
from zoneinfo import ZoneInfo

SEED_PATH = Path(__file__).parent / "seed" / "places.json"


@dataclass(frozen=True)
class PlaceInfo:
    tz: ZoneInfo
    airport: tuple[float, float] | None
    by_boat: bool = False

    def local(self, moment: datetime) -> datetime:
        return moment.astimezone(self.tz)


@cache
def _seed() -> dict:
    return json.loads(SEED_PATH.read_text(encoding="utf-8"))["places"]


def place_info(place_id: str) -> PlaceInfo:
    entry = _seed().get(place_id)
    if entry is None:  # a city from the route map: its time zone and main airport from Travelpayouts
        from app.destinations import PREFIX
        from app.flights import city

        found = city(place_id.removeprefix(PREFIX).upper())
        return PlaceInfo(tz=ZoneInfo(found.tz), airport=found.airport)
    airport = entry.get("airport")
    return PlaceInfo(
        tz=ZoneInfo(entry["tz"]),
        airport=(airport["lat"], airport["lon"]) if airport else None,
        by_boat=entry.get("transfer") == "boat",
    )
