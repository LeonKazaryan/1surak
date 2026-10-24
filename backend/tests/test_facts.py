from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.facts.model import Fact, FactError, normalize
from app.facts.resolve import resolve

NOW = datetime(2026, 10, 25, 12, tzinfo=UTC)


def fact(value, **overrides) -> Fact:
    base = {
        "entity_type": "place",
        "entity_id": "Q1",
        "attribute": "sea_temp",
        "period": "m11",
        "value": value,
        "unit": "°C",
        "source": "copernicus",
        "source_tier": "official",
        "kind": "real",
        "fetched_at": NOW - timedelta(days=1),
    }
    return Fact(**{**base, **overrides})


def test_should_convert_fahrenheit_to_celsius_at_the_boundary():
    assert normalize(fact(77.0, unit="°F")) == fact(25.0)


def test_should_convert_hours_to_minutes_for_durations():
    normalized = normalize(fact(4.5, attribute="flight_duration", unit="h", period=None))

    assert (normalized.value, normalized.unit) == (270.0, "min")


def test_should_reject_a_unit_the_attribute_cannot_take():
    with pytest.raises(FactError, match="unit"):
        normalize(fact(25.0, unit="km"))


def test_should_reject_a_value_outside_the_attribute_range():
    with pytest.raises(FactError, match="range"):
        normalize(fact(80.0))


def test_should_reject_a_fact_without_a_source():
    with pytest.raises(FactError, match="source"):
        normalize(fact(25.0, source=""))


def test_should_reject_an_unknown_source_tier():
    with pytest.raises(FactError, match="tier"):
        normalize(fact(25.0, source_tier="rumour"))


def test_should_reject_an_unknown_kind():
    with pytest.raises(FactError, match="kind"):
        normalize(fact(25.0, kind="guess"))


def test_should_reject_text_where_the_attribute_expects_a_number():
    with pytest.raises(FactError, match="number"):
        normalize(fact("warm"))


def test_should_store_timestamps_in_utc():
    moscow = timezone(timedelta(hours=3))

    normalized = normalize(fact(25.0, fetched_at=datetime(2026, 10, 25, 12, tzinfo=moscow)))

    assert normalized.fetched_at.utcoffset() == timedelta(0)
    assert normalized.fetched_at.hour == 9


def test_should_read_a_timestamp_without_a_zone_as_utc():
    normalized = normalize(fact(25.0, fetched_at=datetime(2026, 10, 25, 12)))

    assert normalized.fetched_at == datetime(2026, 10, 25, 12, tzinfo=UTC)


@pytest.mark.parametrize(
    "value",
    [float("nan"), float("inf"), {"nested": float("nan")}, {1, 2}, "x" * 5000],
    ids=["nan", "inf", "nested-nan", "set", "too-long"],
)
def test_should_reject_a_value_that_cannot_be_stored(value):
    with pytest.raises(FactError, match="value"):
        normalize(fact(value, attribute="food_options", unit=None, period=None))


def test_should_reject_a_number_too_large_to_convert():
    with pytest.raises(FactError, match="large"):
        normalize(fact(10**400, unit="°F"))


def test_should_reject_a_source_link_that_is_not_http():
    with pytest.raises(FactError, match="source_url"):
        normalize(fact(25.0, source_url="javascript:alert(1)"))


def test_should_accept_an_attribute_nobody_registered_yet():
    new = fact("halal buffet", attribute="food_options", unit=None, period=None)

    assert normalize(new) == new


def test_should_prefer_a_real_value_over_an_estimate():
    real = fact(26.0, source="copernicus", fetched_at=NOW - timedelta(days=30))
    estimate = fact(24.0, source="model", kind="estimated")

    assert resolve([estimate, real], NOW).chosen == real


def test_should_prefer_an_official_source_over_media():
    official = fact(26.0, source="copernicus", fetched_at=NOW - timedelta(days=30))
    media = fact(26.4, source="blog", source_tier="media")

    assert resolve([media, official], NOW).chosen == official


def test_should_prefer_the_newest_value_when_sources_rank_the_same():
    older = fact(26.0, source="a", fetched_at=NOW - timedelta(days=10))
    newer = fact(26.5, source="b", fetched_at=NOW - timedelta(days=1))

    assert resolve([older, newer], NOW).chosen == newer


def test_should_flag_a_conflict_when_sources_disagree_beyond_the_tolerance():
    result = resolve([fact(26.0, source="a"), fact(22.0, source="b", source_tier="media")], NOW)

    assert result.conflict
    assert [f.source for f in result.alternatives] == ["b"]


def test_should_not_flag_differences_inside_the_tolerance():
    result = resolve([fact(26.0, source="a"), fact(25.4, source="b", source_tier="media")], NOW)

    assert not result.conflict


def test_should_compare_text_values_exactly():
    result = resolve(
        [
            fact("visa_free", attribute="visa_rule", unit=None, period=None, source="mfa"),
            fact("e_visa", attribute="visa_rule", unit=None, period=None, source="blog", source_tier="media"),
        ],
        NOW,
    )

    assert result.conflict


def test_should_ignore_expired_values_while_a_fresh_one_exists():
    expired = fact(30.0, source="a", valid_until=NOW - timedelta(hours=1))
    fresh = fact(26.0, source="b", source_tier="media")

    result = resolve([expired, fresh], NOW)

    assert result.chosen == fresh
    assert not result.stale
    assert not result.conflict


def test_should_fall_back_to_an_expired_value_and_mark_it_stale():
    expired = fact(26.0, valid_until=NOW - timedelta(hours=1))

    result = resolve([expired], NOW)

    assert result.chosen == expired
    assert result.stale


def test_should_return_nothing_when_there_are_no_facts():
    assert resolve([], NOW) is None
