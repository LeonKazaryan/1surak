from collections import defaultdict
from datetime import date, datetime
from statistics import fmean

from app.facts.model import Fact, FactError, normalize

SOURCE = "open-meteo-marine"
SOURCE_URL = "https://marine-api.open-meteo.com/v1/marine"
VARIABLE = "sea_surface_temperature_mean"


def _monthly_sea_facts(place_qid: str, payload: dict, fetched_at: datetime) -> list[Fact]:
    daily, unit = payload["daily"], payload["daily_units"][VARIABLE]
    by_month: dict[int, list[float]] = defaultdict(list)
    for day, value in zip(daily["time"], daily[VARIABLE], strict=True):
        if value is not None:
            by_month[date.fromisoformat(day).month].append(value)
    return [
        normalize(
            Fact(
                entity_type="place",
                entity_id=place_qid,
                attribute="sea_temp",
                period=f"m{month}",
                value=fmean(values),
                unit=unit,
                source=SOURCE,
                source_url=SOURCE_URL,
                source_tier="official",
                kind="real",
                fetched_at=fetched_at,
            )
        )
        for month, values in sorted(by_month.items())
    ]


def monthly_sea_temp(place_qid: str, payload: dict, fetched_at: datetime) -> list[Fact]:
    """Daily sea surface temperature → one monthly mean per calendar month. Land points give no facts."""
    try:
        return _monthly_sea_facts(place_qid, payload, fetched_at)
    except (KeyError, TypeError, ValueError) as error:
        raise FactError(f"malformed open-meteo marine payload: {error!r:.200}") from error
