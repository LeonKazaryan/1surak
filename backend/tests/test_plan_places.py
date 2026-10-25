from datetime import datetime
from zoneinfo import ZoneInfo

from app.catalog.catalog import load_catalog
from app.plan.places import place_info


def test_should_know_the_time_zone_of_every_catalogue_place():
    for place in load_catalog().places:
        assert isinstance(place_info(place.id).tz, ZoneInfo), place.id


def test_should_know_where_the_airport_of_every_flying_place_is():
    for place in load_catalog().places:
        if place.airport:
            assert place_info(place.id).airport is not None, place.id


def test_should_tell_the_local_time_at_the_destination():
    landing = datetime.fromisoformat("2026-11-06T09:00:00+05:00")  # 09:00 in Astana

    assert place_info("antalya").local(landing).strftime("%H:%M") == "07:00"


def test_should_send_island_resorts_by_boat():
    assert place_info("maldives").by_boat
    assert not place_info("antalya").by_boat
