"""Checks on the committed catalogue: the completeness gate from docs/08-data-model.md."""

from collections import defaultdict

import pytest

from app.catalog.catalog import CURATED_PATH, KIND_LABELS, _read, curated_facts, load_catalog, seed_facts
from app.facts.model import normalize

# The Open-Meteo marine model doesn't cover the Caspian, which counts as a lake.
NO_SEA_DATA = {"dagestan", "baku"}


@pytest.fixture(scope="module")
def catalog():
    return load_catalog()


@pytest.fixture(scope="module")
def climate():
    by_place: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for fact in seed_facts():
        by_place[fact.entity_id][fact.attribute].add(fact.period)
    return by_place


def test_should_have_unique_ids_and_qids(catalog):
    ids = [p.id for p in catalog.places]
    qids = [p.qid for p in catalog.places]
    assert len(ids) == len(set(ids))
    assert len(qids) == len(set(qids))
    assert len(ids) >= 40


def test_should_use_known_kinds_and_levels(catalog):
    for place in catalog.places:
        assert place.kinds and set(place.kinds) <= set(KIND_LABELS), place.id
        assert place.price_level in (1, 2, 3), place.id
        assert place.kids in ("good", "ok", "poor"), place.id
        assert place.highlights and place.watch_out, place.id


def test_should_reach_every_place_from_moscow(catalog):
    for place in catalog.places:
        assert place.flight_min or place.train_min, place.id
        if place.flight_min:
            assert place.airport, place.id


def test_should_have_twelve_months_of_climate_for_every_place(catalog, climate):
    months = {f"m{m}" for m in range(1, 13)}
    for place in catalog.places:
        for attribute in ("air_max", "air_min", "rain_days"):
            assert climate[place.qid][attribute] == months, f"{place.id} {attribute}"


def test_should_have_sea_temperature_for_every_sea_place(catalog, climate):
    months = {f"m{m}" for m in range(1, 13)}
    for place in catalog.places:
        if "sea" in place.kinds and place.id not in NO_SEA_DATA:
            assert climate[place.qid]["sea_temp"] == months, place.id


def test_should_keep_every_fact_valid_and_sourced(catalog):
    for fact in [*curated_facts(catalog), *seed_facts()]:
        normalize(fact)  # raises on a bad unit, range or source
        assert fact.source


def test_should_not_use_long_dashes_in_user_facing_text():
    assert "—" not in CURATED_PATH.read_text(encoding="utf-8").split('"places"', 1)[1]


def test_should_define_every_country_a_place_uses(catalog):
    used = {p.country.code for p in catalog.places}
    assert used <= set(_read(CURATED_PATH)["countries"])
