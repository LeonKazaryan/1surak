import json
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any

TIERS = ("official", "media", "community")
KINDS = ("real", "estimated", "synthetic")
MAX_VALUE_CHARS = 2000


class FactError(ValueError):
    pass


@dataclass(frozen=True)
class Fact:
    entity_type: str
    entity_id: str
    attribute: str
    value: Any
    unit: str | None
    source: str
    source_tier: str
    kind: str
    fetched_at: datetime
    period: str | None = None
    source_url: str | None = None
    valid_until: datetime | None = None

    @property
    def key(self) -> tuple[str, str | None]:
        return (self.attribute, self.period)


@dataclass(frozen=True)
class Attribute:
    unit: str
    minimum: float
    maximum: float
    tolerance: float = 0.0


ATTRIBUTES: dict[str, Attribute] = {
    "air_max": Attribute("°C", -60, 60, tolerance=1.5),
    "air_min": Attribute("°C", -70, 50, tolerance=1.5),
    "sea_temp": Attribute("°C", -2, 35, tolerance=1.0),
    "rain_days": Attribute("days", 0, 31, tolerance=2),
    "flight_duration": Attribute("min", 10, 1500, tolerance=30),
    "visa_days": Attribute("days", 0, 366),
}

CONVERSIONS: dict[tuple[str, str], Callable[[float], float]] = {
    ("°F", "°C"): lambda v: (v - 32) * 5 / 9,
    ("h", "min"): lambda v: v * 60,
    ("s", "min"): lambda v: v / 60,
    ("inch", "mm"): lambda v: v * 25.4,
}


def is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def convert(value: float, unit: str | None, target: str) -> float:
    if unit == target:
        return value
    converter = CONVERSIONS.get((unit, target)) if unit else None
    if converter is None:
        raise FactError(f"cannot convert unit {unit!r} to {target!r}")
    try:
        return converter(value)
    except OverflowError as error:
        raise FactError(f"{value!r} {unit} is too large to convert") from error


def _utc(moment: datetime | None) -> datetime | None:
    if moment is None:
        return None
    return moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment.astimezone(UTC)


def _check_storable(value: Any) -> None:
    try:
        size = len(json.dumps(value, allow_nan=False))
    except (TypeError, ValueError, RecursionError) as error:
        raise FactError(f"value {value!r:.80} cannot be stored as JSON") from error
    if size > MAX_VALUE_CHARS:
        raise FactError(f"value is {size} characters, the limit is {MAX_VALUE_CHARS}")


def normalize(fact: Fact) -> Fact:
    if not fact.source:
        raise FactError("a fact needs a source")
    if fact.source_tier not in TIERS:
        raise FactError(f"unknown source tier {fact.source_tier!r}")
    if fact.kind not in KINDS:
        raise FactError(f"unknown kind {fact.kind!r}")
    if fact.source_url and not fact.source_url.startswith(("https://", "http://")):
        raise FactError(f"source_url must be an http(s) link, got {fact.source_url!r:.80}")
    _check_storable(fact.value)
    stamped = replace(fact, fetched_at=_utc(fact.fetched_at), valid_until=_utc(fact.valid_until))
    spec = ATTRIBUTES.get(fact.attribute)
    if spec is None:
        return stamped
    if not is_number(fact.value):
        raise FactError(f"{fact.attribute} expects a number, got {fact.value!r}")
    value = convert(fact.value, fact.unit, spec.unit)
    if not spec.minimum <= value <= spec.maximum:
        raise FactError(f"{fact.attribute}={value} is outside the range {spec.minimum} to {spec.maximum}")
    return replace(stamped, value=value, unit=spec.unit)
