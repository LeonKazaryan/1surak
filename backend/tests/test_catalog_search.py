from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.catalog.catalog import Country, Place
from app.catalog.search import SearchQuery, Snapshot, build_snapshot, search
from app.facts.model import Fact
from app.facts.resolve import resolve

NOV = 11
NOW = datetime(2026, 10, 25, tzinfo=UTC)
EGYPT = Country("EG", "Египет", "on_arrival", 30, "виза в аэропорту")
TURKEY = Country("TR", "Турция", "visa_free", 60, "")
RUSSIA = Country("RU", "Россия", "none", None, "")


def place(id: str, country: Country = TURKEY, kinds=("sea",), price=2, kids="good") -> Place:
    return Place(
        id=id,
        qid=f"Q{id}",
        name=id.title(),
        country=country,
        kinds=tuple(kinds),
        airport=None,
        lat=0,
        lon=0,
        price_level=price,
        kids=kids,
        highlights=(),
        watch_out=(),
        flight_min=None,
        direct=True,
        train_min=None,
    )


def snap(p: Place, sea=None, air=None, flight=None, train=None, direct=True) -> Snapshot:
    climate = {}
    if sea is not None or air is not None:
        climate[NOV] = {k: v for k, v in (("sea_temp", sea), ("air_max", air)) if v is not None}
    return Snapshot(
        place=p,
        climate=climate,
        flight_min=flight,
        direct=direct,
        train_min=train,
        visa_rule=p.country.visa,
        visa_days=p.country.visa_days,
        visa_note=p.country.visa_note,
    )


@pytest.fixture
def world() -> list[Snapshot]:
    return [
        snap(place("hurghada", EGYPT, price=1), sea=26, air=28, flight=300),
        snap(place("antalya"), sea=21, air=21, flight=240),
        snap(place("phuket"), sea=29, air=31, flight=560),
        snap(place("dubai", price=3), sea=27, air=30, flight=300),
        snap(place("sochi", RUSSIA, kinds=("sea", "mountains")), sea=15, air=15, flight=150, train=1440),
        snap(place("kazan", RUSSIA, kinds=("city",), price=1), air=3, flight=90, train=720),
        snap(place("kamchatka", RUSSIA, kinds=("nature",), kids="poor"), air=0, flight=520),
    ]


def golden() -> SearchQuery:
    return SearchQuery(month=NOV, min_sea_temp=24, max_flight_hours=6, with_kids=True, max_price_level=2)


def test_should_match_the_golden_query_and_explain_every_near_miss(world):
    result = search(world, golden())

    assert [m["id"] for m in result["matches"]] == ["hurghada"]
    hurghada = result["matches"][0]
    assert hurghada["climate"] == {"month": "ноябрь", "днём": 28, "море": 26}
    assert hurghada["flight_hours"] == 5
    assert hurghada["visa"].startswith("виза по прибытии, до 30 дней")

    why = {m["id"]: m["why_not"] for m in result["near_misses"]}
    assert why["antalya"] == "море в ноябре около 21 °C, нужно от 24 °C"
    assert why["phuket"] == "перелёт около 9.5 ч, нужно до 6 ч"
    assert why["dubai"] == "дорого (цены 3 из 3)"
    assert "sochi" not in why  # 9 °C too cold is a different trip, not a near miss
    assert "kazan" not in why  # misses on two counts (no sea data, not a sea place), so it isn't "near"


def test_should_rank_other_trips_by_travel_time_then_price(world):
    result = search(world, SearchQuery(region="russia", limit=10))

    assert [m["id"] for m in result["matches"]] == ["kazan", "sochi", "kamchatka"]


def test_should_say_when_sea_data_is_missing_instead_of_guessing(world):
    world.append(snap(place("dagestan", RUSSIA, kinds=("sea", "mountains"), price=1), air=13, flight=150))

    result = search(world, SearchQuery(month=NOV, min_sea_temp=14, region="russia"))

    assert [m["id"] for m in result["matches"]] == ["sochi"]
    why = {m["id"]: m["why_not"] for m in result["near_misses"]}
    assert why == {"dagestan": "нет данных: температура моря"}


def test_should_require_a_month_for_temperature_filters():
    with pytest.raises(ValidationError, match="month is required"):
        SearchQuery(min_sea_temp=24)


def test_should_keep_visa_on_arrival_out_of_no_visa(world):
    ids = {m["id"] for m in search(world, SearchQuery(visa="no_visa", limit=10))["matches"]}
    easy = {m["id"] for m in search(world, SearchQuery(visa="easy", limit=10))["matches"]}

    assert "hurghada" not in ids
    assert "hurghada" in easy


def test_should_only_offer_train_destinations_without_flight(world):
    result = search(world, SearchQuery(without_flight=True, limit=10))

    assert [m["id"] for m in result["matches"]] == ["kazan", "sochi"]
    assert result["matches"][0]["train_hours"] == 12


def test_should_leave_out_excluded_destinations_by_id_or_name(world):
    result = search(world, SearchQuery(kinds=["sea"], exclude=["hurghada", "Antalya"], limit=10))

    ids = [m["id"] for m in result["matches"]]
    assert "hurghada" not in ids and "antalya" not in ids


def test_should_skip_poor_kids_fit_only_when_travelling_with_kids(world):
    assert "kamchatka" in {m["id"] for m in search(world, SearchQuery(kinds=["nature"]))["matches"]}
    result = search(world, SearchQuery(kinds=["nature"], with_kids=True))
    assert result["matches"] == []
    assert result["near_misses"] == [
        {"id": "kamchatka", "name": "Kamchatka", "why_not": "не для маленьких детей"}
    ]


def test_should_cap_results_and_report_how_many_more(world):
    result = search(world, SearchQuery(limit=2))

    assert len(result["matches"]) == 2
    assert result["more_matches"] == len(world) - 2


def fact(attribute: str, value, source: str, kind="real", tier="official", period="m11") -> Fact:
    return Fact(
        entity_type="place",
        entity_id="Qx",
        attribute=attribute,
        period=period,
        value=value,
        unit="°C",
        source=source,
        source_tier=tier,
        kind=kind,
        fetched_at=NOW,
    )


def test_should_flag_sources_that_disagree():
    facts = [fact("sea_temp", 26.0, "open-meteo-marine"), fact("sea_temp", 23.0, "copernicus")]
    resolved = {("sea_temp", "m11"): resolve(facts, NOW)}

    snapshot = build_snapshot(place("x"), resolved, {}, {})

    assert snapshot.climate[NOV]["sea_temp"] in (26.0, 23.0)
    assert len(snapshot.flags) == 1 and "источники расходятся" in snapshot.flags[0]


def test_should_not_round_a_near_miss_up_to_the_threshold(world):
    world.append(snap(place("alanya", price=1), sea=23.6, air=22, flight=240))

    result = search(world, golden())

    why = {m["id"]: m["why_not"] for m in result["near_misses"]}
    assert why["alanya"] == "море в ноябре около 23.6 °C, нужно от 24 °C"


def test_should_show_the_closest_miss_of_each_kind_first(world):
    world += [snap(place(f"cold{i}", price=1), sea=22 - i, air=22, flight=200) for i in range(6)]

    result = search(world, golden())

    reasons = [m["why_not"] for m in result["near_misses"]]
    assert reasons[0] == "море в ноябре около 22 °C, нужно от 24 °C"
    assert any(r.startswith("перелёт") for r in reasons[:3])
    assert any(r.startswith("дорого") for r in reasons[:3])


def test_should_not_call_a_far_miss_near(world):
    result = search(world, SearchQuery(without_flight=True, kinds=["sea"], limit=10))

    assert [m["id"] for m in result["matches"]] == ["sochi"]
    assert result["near_misses"] == []  # «no train there» is a different trip, not a near miss


def test_should_rank_a_sea_trip_by_how_warm_the_sea_is_before_flight_time(world):
    result = search(world, SearchQuery(month=NOV, kinds=["sea"], limit=10))

    ids = [m["id"] for m in result["matches"]]
    assert ids.index("hurghada") < ids.index("antalya") < ids.index("sochi")  # 26 °C, 21 °C, 15 °C
    assert ids[:3] == ["hurghada", "dubai", "phuket"]  # all ≥ 24 °C, then by flight time


def test_should_tell_the_agent_to_ask_for_the_kids_age_when_it_is_unknown(world):
    without_age = search(world, golden())
    with_age = search(world, golden().model_copy(update={"kids_ages": [5]}))

    assert without_age["missing"][0].startswith("возраст детей")
    assert without_age["ask"] == "Закончи ответ одним вопросом про возраст детей."
    assert "missing" not in with_age and "ask" not in with_age


def test_should_tell_the_agent_to_ask_when_to_go_without_a_month(world):
    assert search(world, SearchQuery(kinds=["sea"]))["missing"] == ["когда ехать"]
