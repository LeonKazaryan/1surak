from calendar import monthrange
from collections import defaultdict
from datetime import date, datetime
from statistics import fmean

from app.facts.model import Fact, FactError, convert, normalize

SOURCE = "open-meteo-era5"
SOURCE_URL = "https://archive-api.open-meteo.com/v1/archive"
RAIN_DAY_MM = 1.0
MEAN_VARIABLES = {"temperature_2m_max": "air_max", "temperature_2m_min": "air_min"}


def _fact(place_qid: str, attribute: str, month: int, value: float, unit: str, fetched_at: datetime) -> Fact:
    return normalize(
        Fact(
            entity_type="place",
            entity_id=place_qid,
            attribute=attribute,
            period=f"m{month}",
            value=value,
            unit=unit,
            source=SOURCE,
            source_url=SOURCE_URL,
            source_tier="official",
            kind="real",
            fetched_at=fetched_at,
        )
    )


def _monthly_means(days: list[str], values: list[float | None]) -> dict[int, float]:
    by_month: dict[int, list[float]] = defaultdict(list)
    for day, value in zip(days, values, strict=True):
        if value is not None:
            by_month[date.fromisoformat(day).month].append(value)
    return {month: fmean(vals) for month, vals in by_month.items()}


def _rain_days(days: list[str], rain: list[float | None], unit: str) -> dict[int, float]:
    wet_by_year: dict[tuple[int, int], list[bool]] = defaultdict(list)
    for day, value in zip(days, rain, strict=True):
        if value is not None:
            parsed = date.fromisoformat(day)
            wet_by_year[(parsed.year, parsed.month)].append(convert(value, unit, "mm") > RAIN_DAY_MM)
    by_month: dict[int, list[float]] = defaultdict(list)
    for (year, month), wet in wet_by_year.items():
        by_month[month].append(fmean(wet) * monthrange(year, month)[1])
    return {month: fmean(counts) for month, counts in by_month.items()}


def _climate_facts(place_qid: str, payload: dict, fetched_at: datetime) -> list[Fact]:
    daily, units = payload["daily"], payload["daily_units"]
    days = daily["time"]
    result = [
        _fact(place_qid, attribute, month, value, units[variable], fetched_at)
        for variable, attribute in MEAN_VARIABLES.items()
        for month, value in _monthly_means(days, daily[variable]).items()
    ]
    rain = _rain_days(days, daily["precipitation_sum"], units["precipitation_sum"])
    return result + [
        _fact(place_qid, "rain_days", month, value, "days", fetched_at) for month, value in rain.items()
    ]


def monthly_climate(place_qid: str, payload: dict, fetched_at: datetime) -> list[Fact]:
    try:
        return _climate_facts(place_qid, payload, fetched_at)
    except (KeyError, TypeError, ValueError) as error:
        raise FactError(f"malformed open-meteo payload: {error!r:.200}") from error
