from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.facts.model import ATTRIBUTES, KINDS, TIERS, Fact, is_number


@dataclass(frozen=True)
class Resolution:
    chosen: Fact
    alternatives: list[Fact]
    conflict: bool
    stale: bool


def _rank(fact: Fact) -> tuple[int, int, float]:
    return (KINDS.index(fact.kind), TIERS.index(fact.source_tier), -fact.fetched_at.timestamp())


def _differs(a: Any, b: Any, tolerance: float) -> bool:
    if is_number(a) and is_number(b):
        return abs(a - b) > tolerance
    return a != b


def resolve(facts: list[Fact], now: datetime) -> Resolution | None:
    if not facts:
        return None
    fresh = [f for f in facts if f.valid_until is None or f.valid_until > now]
    chosen, *others = sorted(fresh or facts, key=_rank)
    spec = ATTRIBUTES.get(chosen.attribute)
    tolerance = spec.tolerance if spec else 0.0
    return Resolution(
        chosen=chosen,
        alternatives=others,
        conflict=any(_differs(chosen.value, f.value, tolerance) for f in others),
        stale=not fresh,
    )
