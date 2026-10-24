from datetime import UTC, datetime

import pytest

from app.facts.adapters import open_meteo
from app.facts.model import FactError

FETCHED = datetime(2026, 10, 25, tzinfo=UTC)


def payload(units: dict | None = None, **daily) -> dict:
    return {
        "daily_units": units
        or {"temperature_2m_max": "°C", "temperature_2m_min": "°C", "precipitation_sum": "mm"},
        "daily": {
            "time": ["2024-11-01", "2024-11-02", "2025-11-01", "2025-11-02", "2025-12-01"],
            "temperature_2m_max": [26.0, 28.0, 27.0, 29.0, 20.0],
            "temperature_2m_min": [18.0, 20.0, 19.0, 21.0, 12.0],
            "precipitation_sum": [0.0, 5.0, 2.0, 0.4, 0.0],
            **daily,
        },
    }


def by_key(facts):
    return {(f.attribute, f.period): f for f in facts}


def test_should_turn_daily_data_into_monthly_means():
    facts = by_key(open_meteo.monthly_climate("Q1", payload(), FETCHED))

    assert facts[("air_max", "m11")].value == pytest.approx(27.5)
    assert facts[("air_min", "m11")].value == pytest.approx(19.5)
    assert facts[("air_max", "m12")].value == pytest.approx(20.0)


def test_should_scale_rainy_days_to_the_whole_month_when_days_are_missing():
    facts = by_key(open_meteo.monthly_climate("Q1", payload(), FETCHED))

    assert facts[("rain_days", "m11")].value == pytest.approx(15.0)
    assert facts[("rain_days", "m12")].value == pytest.approx(0.0)


def test_should_read_units_from_the_response_instead_of_assuming_them():
    fahrenheit = payload(
        units={"temperature_2m_max": "°F", "temperature_2m_min": "°F", "precipitation_sum": "mm"},
        temperature_2m_max=[77.0, 77.0, 77.0, 77.0, 68.0],
    )

    facts = by_key(open_meteo.monthly_climate("Q1", fahrenheit, FETCHED))

    assert (facts[("air_max", "m11")].value, facts[("air_max", "m11")].unit) == (pytest.approx(25.0), "°C")


def test_should_count_rainy_days_when_rain_comes_in_inches():
    inches = payload(
        units={"temperature_2m_max": "°C", "temperature_2m_min": "°C", "precipitation_sum": "inch"},
        precipitation_sum=[0.0, 0.2, 0.08, 0.01, 0.0],
    )

    facts = by_key(open_meteo.monthly_climate("Q1", inches, FETCHED))

    assert facts[("rain_days", "m11")].value == pytest.approx(15.0)


def test_should_skip_missing_days():
    facts = by_key(
        open_meteo.monthly_climate("Q1", payload(temperature_2m_max=[26.0, None, None, 28.0, None]), FETCHED)
    )

    assert facts[("air_max", "m11")].value == pytest.approx(27.0)
    assert ("air_max", "m12") not in facts


def test_should_tag_every_fact_with_its_source():
    facts = open_meteo.monthly_climate("Q1", payload(), FETCHED)

    assert {(f.source, f.kind, f.entity_id, f.fetched_at) for f in facts} == {
        ("open-meteo-era5", "real", "Q1", FETCHED)
    }


@pytest.mark.parametrize(
    "broken",
    [
        {"error": True, "reason": "Parameter 'daily' is invalid"},
        payload(temperature_2m_max=[26.0]),
        payload(time=["2024-13-01", "2024-11-02", "2025-11-01", "2025-11-02", "2025-12-01"]),
        payload(precipitation_sum=["wet", 0.0, 0.0, 0.0, 0.0]),
    ],
)
def test_should_raise_one_clear_error_for_a_malformed_payload(broken):
    with pytest.raises(FactError, match="open-meteo"):
        open_meteo.monthly_climate("Q1", broken, FETCHED)
