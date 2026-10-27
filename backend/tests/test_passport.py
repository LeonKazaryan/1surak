"""The trip as the chat's header shows it, field by field."""

from app.tools.registry import fact
from app.trip.brief import TripBrief
from app.trip.passport import passport


def test_should_show_the_trip_field_by_field():
    brief = TripBrief(
        destination="Казахстан",
        month=11,
        nights_min=11,
        nights_max=14,
        adults=1,
        budget_level=2,
        origin_code="MOW",
        visa_free_only=True,
    )

    shown = passport(brief)

    assert shown["destination"]["country_code"] == "KZ" and shown["destination"]["photo"]["url"]
    assert (shown["when"], shown["travelers"], shown["budget"]) == (
        "Ноябрь · 11–14 ночей",
        "1 взрослый",
        "Средний бюджет",
    )
    assert shown["origin"]["from"] == "из Москвы" and shown["origin"]["lat"] > 55 and shown["visa_free_only"]
    assert (
        40 < shown["destination"]["lat"] < 56 and 46 < shown["destination"]["lon"] < 88
    )  # within Kazakhstan


def test_should_flag_a_city_by_its_country_and_leave_the_unknown_empty():
    assert passport(TripBrief(destination="Нью-Йорк"))["destination"]["country_code"] == "US"
    empty = passport(TripBrief())
    assert empty["destination"] is None and empty["when"] is None and empty["origin"] is None


def test_should_count_a_fact_in_good_russian():
    assert (
        fact(1, ("направление", "направления", "направлений"), "из города")["label"]
        == "направление из города"
    )
    assert fact(14, ("место", "места", "мест"))["label"] == "мест"
    assert fact(22, ("маршрут", "маршрута", "маршрутов"))["label"] == "маршрута"
