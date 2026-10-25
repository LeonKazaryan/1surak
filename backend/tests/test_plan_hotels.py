from app.catalog.catalog import load_catalog
from app.plan.hotels import Party, Wishes, choose_hotel, hotels_for, wishes_from

CATALOG = load_catalog()
ANTALYA = CATALOG.find("antalya")
SPB = CATALOG.find("spb")
COUPLE = Party(adults=2)
FAMILY = Party(adults=2, children_ages=(5,))


def test_should_build_the_same_hotels_every_time():
    first, again = hotels_for(ANTALYA, 11), hotels_for(ANTALYA, 11)

    assert [h.id for h in first] == [h.id for h in again]
    assert [h.rates for h in first] == [h.rates for h in again]
    assert len({h.name for h in first}) == len(first) >= 5


def test_should_never_offer_an_adults_only_hotel_to_a_family():
    hotels = hotels_for(ANTALYA, 11)
    assert any(h.adults_only for h in hotels)

    pick = choose_hotel(hotels, FAMILY, Wishes(), level=2, nights=7)

    shown = [pick.best, *pick.alternatives]
    assert not any(c.hotel.adults_only for c in shown)
    assert any("только для взрослых" in reason for _, reason in pick.excluded)


def test_should_take_all_inclusive_when_asked_and_say_so_when_there_is_none():
    resort = choose_hotel(hotels_for(ANTALYA, 11), COUPLE, Wishes(all_inclusive=True), level=2, nights=7)
    city = choose_hotel(hotels_for(SPB, 11), COUPLE, Wishes(all_inclusive=True), level=2, nights=3)

    assert resort.best.rate.meal == "all_inclusive"
    assert not resort.unmet
    assert city.best.rate.meal != "all_inclusive"
    assert any("всё включено" in text for text in city.unmet)


def test_should_pick_the_stars_by_the_budget():
    cheap = choose_hotel(hotels_for(ANTALYA, 11), COUPLE, Wishes(), level=1, nights=7)
    comfort = choose_hotel(hotels_for(ANTALYA, 11), COUPLE, Wishes(), level=3, nights=7)

    assert cheap.best.hotel.stars < comfort.best.hotel.stars
    assert cheap.best.total_rub < comfort.best.total_rub


def test_should_price_the_whole_stay_for_the_party():
    pick = choose_hotel(hotels_for(ANTALYA, 11), COUPLE, Wishes(), level=2, nights=7)

    assert pick.best.total_rub == pick.best.night_rub * 7
    assert pick.best.rooms == 1


def test_should_book_two_rooms_for_five_guests():
    pick = choose_hotel(
        hotels_for(ANTALYA, 11), Party(adults=4, children_ages=(8,)), Wishes(), level=2, nights=7
    )

    assert pick.best.rooms == 2


def test_should_keep_the_hotel_the_user_chose():
    hotels = hotels_for(ANTALYA, 11)
    chosen = next(h for h in hotels if not h.adults_only and h.stars == 3)

    pick = choose_hotel(hotels, COUPLE, Wishes(), level=3, nights=7, prefer=chosen.id)

    assert pick.best.hotel.id == chosen.id


def test_should_say_why_the_hotel_fits_a_family():
    pick = choose_hotel(hotels_for(ANTALYA, 11), FAMILY, Wishes(), level=2, nights=7)

    assert pick.best.reasons
    assert pick.best.hotel.kids_club or any("детского клуба" in miss for miss in pick.best.misses)


def test_should_only_offer_hotels_that_take_pets():
    pick = choose_hotel(hotels_for(ANTALYA, 11), COUPLE, Wishes(pets=True), level=2, nights=7)

    assert pick.best.hotel.pets or any("животн" in text for text in pick.unmet)
    assert all(c.hotel.pets for c in [pick.best, *pick.alternatives]) or pick.unmet


def test_should_read_hotel_wishes_from_the_users_words():
    wishes = wishes_from(["всё включено", "с собакой", "первая линия", "тихий отель"])

    assert wishes == Wishes(all_inclusive=True, pets=True, beach=True, quiet=True)
    assert wishes_from(None) == Wishes()
