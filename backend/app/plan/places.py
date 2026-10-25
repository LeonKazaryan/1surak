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
    entry = _seed()[place_id]
    airport = entry.get("airport")
    return PlaceInfo(
        tz=ZoneInfo(entry["tz"]),
        airport=(airport["lat"], airport["lon"]) if airport else None,
        by_boat=entry.get("transfer") == "boat",
    )
