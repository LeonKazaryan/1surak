from datetime import time

from app.catalog.catalog import load_catalog
from app.flights import Ticket
from app.plan.checks import arrival_checks, departure_checks
from app.plan.hotels import Party, hotels_for
from app.plan.places import place_info
from app.plan.transfers import transfer_to

CATALOG = load_catalog()
ANTALYA = CATALOG.find("antalya")
HOTEL = next(h for h in hotels_for(ANTALYA, 11) if h.reception_24h)


def ticket(departure_at: str, minutes: int, price: int = 30_000) -> Ticket:
    return Ticket("NQZ", "AYT", "PC", "1", departure_at, price, 0, minutes, "/t")


def test_should_estimate_the_ride_from_the_airport_to_the_hotel():
    ride = transfer_to(HOTEL, ANTALYA, place_info("antalya"), Party(adults=2))

    assert ride.mode == "car"
    assert 5 <= ride.km <= 40
    assert 15 <= ride.minutes <= 90
    assert ride.price_rub >= 800


def test_should_take_island_resorts_by_boat():
    maldives = CATALOG.find("maldives")
    hotel = hotels_for(maldives, 2)[0]

    ride = transfer_to(hotel, maldives, place_info("maldives"), Party(adults=2))

    assert ride.mode == "boat"


def test_should_offer_an_early_check_in_when_the_plane_lands_in_the_morning():
    landing = ticket("2026-11-06T03:00:00+05:00", 330)  # 06:30 in Antalya

    checks = arrival_checks(landing, HOTEL, place_info("antalya"), transfer_minutes=30)

    early = next(c for c in checks if c.fix and c.fix["type"] == "early_check_in")
    assert early.level == "warn"
    assert "07:00" in early.text and "14:00" in early.text
    assert early.fix["price_rub"] == HOTEL.early_check_in_rub
    assert early.fix["id"] == f"early_check_in:{HOTEL.id}" and HOTEL.name in early.fix["label"]


def test_should_say_the_hotel_waits_for_a_late_arrival():
    landing = ticket("2026-11-06T18:00:00+05:00", 330)  # 21:30 in Antalya, at the hotel by 22:00

    checks = arrival_checks(landing, HOTEL, place_info("antalya"), transfer_minutes=30)

    assert all(c.level != "warn" for c in checks)
    late = ticket("2026-11-06T20:30:00+05:00", 330)  # 00:00 in Antalya
    night = arrival_checks(late, HOTEL, place_info("antalya"), transfer_minutes=30)
    assert any("ночью" in c.text for c in night)


def test_should_offer_a_late_check_out_before_an_evening_flight():
    back = ticket("2026-11-13T21:00:00+03:00", 300)

    checks = departure_checks(back, HOTEL, place_info("antalya"), transfer_minutes=30, abroad=True)

    late = next(c for c in checks if c.fix and c.fix["type"] == "late_check_out")
    assert "18:00" in late.text and HOTEL.check_out == time(12)


def test_should_pass_a_morning_flight_after_breakfast():
    back = ticket("2026-11-13T15:00:00+03:00", 300)

    checks = departure_checks(back, HOTEL, place_info("antalya"), transfer_minutes=30, abroad=True)

    assert [c.level for c in checks] == ["ok"]


def test_should_keep_the_room_for_the_night_before_a_flight_after_midnight():
    back = Ticket("AYT", "NQZ", "PC", "2", "2026-11-14T01:30:00+03:00", 30_000, 0, 300, "/t")

    checks = departure_checks(back, HOTEL, place_info("antalya"), transfer_minutes=30, abroad=True)

    assert [c.level for c in checks] == ["ok"]
    assert "22:30" in checks[0].text
    assert not checks[0].fix


def test_should_pack_breakfast_when_the_airport_ride_starts_before_breakfast():
    back = ticket("2026-11-13T09:40:00+03:00", 300)  # leave the hotel at 06:35

    checks = departure_checks(back, HOTEL, place_info("antalya"), transfer_minutes=35, abroad=True)

    assert [c.level for c in checks] == ["info"]
    assert "06:35" in checks[0].text and "завтрак с собой" in checks[0].text
