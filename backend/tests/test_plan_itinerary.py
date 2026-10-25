from dataclasses import replace
from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.plan.guide import Dish, Guide, Spot
from app.plan.hotels import Party
from app.plan.itinerary import Stay, plan_days

TZ = ZoneInfo("Europe/Istanbul")
SIGHTS = tuple(
    Spot(f"s{i}", "see", f"Место {i}", f"Описание {i}.", 36.88 + i / 100, 30.70, star=i == 3)
    for i in range(1, 7)
) + (Spot("trip", "vicinity", "Термессос", "Античный город в горах.", 36.98, 30.46, star=True),)
FOOD = (
    Spot("f1", "eat", "Piyazcı Sami", "Кюфта и пияз."),
    Spot("f2", "eat", "Paçacı Şemsi", "Кебаб и супы."),
)
GUIDE = Guide("antalya", SIGHTS, FOOD, (Dish("Йорук-кебаб", "баранина с овощами"),))


BASE = Stay(
    guide=GUIDE,
    check_in=date(2026, 11, 6),
    check_out=date(2026, 11, 13),
    arrive=datetime(2026, 11, 6, 13, 0, tzinfo=TZ),
    leave=datetime(2026, 11, 13, 15, 0, tzinfo=TZ),
    hotel_at=(36.88, 30.70),
    sea=True,
    sea_warm=True,
)


def stay(**changes) -> Stay:
    return replace(BASE, **changes)


def kinds(day) -> list[str]:
    return [item.kind for item in day.items]


def spot_ids(days) -> list[str]:
    return [
        item.spot_id for day in days for item in day.items if item.spot_id and item.kind in ("sight", "trip")
    ]


def test_should_plan_every_day_from_arrival_to_departure():
    days = plan_days(stay(), Party(adults=2))

    assert [d.date for d in days] == [date(2026, 11, d) for d in range(6, 14)]


def test_should_never_send_the_party_to_the_same_sight_twice():
    ids = spot_ids(plan_days(stay(), Party(adults=2)))

    assert len(ids) == len(set(ids))


def test_should_start_with_the_sights_guides_star():
    days = plan_days(stay(), Party(adults=2))

    assert next(i.spot_id for d in days for i in d.items if i.kind == "sight") == "s3"


def test_should_keep_days_with_small_children_light_and_by_the_sea():
    days = plan_days(stay(), Party(adults=2, children_ages=(4,)))

    full = days[1:-1]
    assert all(kinds(d).count("sight") <= 1 for d in full)
    assert all("beach" in kinds(d) for d in full)
    assert not any("trip" in kinds(d) for d in days)


def test_should_take_adults_on_a_day_trip_when_there_is_time():
    days = plan_days(stay(), Party(adults=2))

    trip_days = [d for d in days if "trip" in kinds(d)]
    assert len(trip_days) == 1
    assert "Термессос" in trip_days[0].title


def test_should_eat_at_local_places_then_suggest_local_dishes():
    meals = [i for d in plan_days(stay(), Party(adults=2)) for i in d.items if i.kind == "food"]

    assert [m.spot_id for m in meals[:2]] == ["f1", "f2"]
    assert any("Йорук-кебаб" in m.title or "Йорук-кебаб" in (m.note or "") for m in meals[2:])


def test_should_fill_the_first_day_only_after_landing():
    days = plan_days(stay(arrive=datetime(2026, 11, 6, 20, 0, tzinfo=TZ)), Party(adults=2))

    assert kinds(days[0]) == ["food"]


def test_should_end_the_last_day_before_the_ride_to_the_airport():
    days = plan_days(stay(leave=datetime(2026, 11, 13, 11, 0, tzinfo=TZ)), Party(adults=2))

    assert kinds(days[-1]) == []


def test_should_still_plan_a_place_without_a_guide():
    days = plan_days(stay(guide=Guide("nowhere")), Party(adults=2))

    assert len(days) == 8
    assert all(item.kind in ("food", "beach", "free", "walk") for d in days for item in d.items)


def test_should_take_an_all_inclusive_party_out_to_dinner_now_and_then():
    late = stay(all_inclusive=True, arrive=datetime(2026, 11, 6, 15, 0, tzinfo=TZ))  # no lunch on day one
    meals = [
        i for d in plan_days(late, Party(adults=2, children_ages=(4,))) for i in d.items if i.kind == "food"
    ]

    out = [m for m in meals if m.spot_id]
    assert out and out[0].title.startswith("Ужин")
    assert len(out) < len(meals) // 2
