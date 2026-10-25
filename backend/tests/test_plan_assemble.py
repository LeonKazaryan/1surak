"""The whole trip from one pick: tickets that follow the nights, a hotel for this party, the rides, the checks,
the days and the bill. Real catalogue places, fake tickets."""

import asyncio
from datetime import date

from app.catalog.catalog import load_catalog
from app.catalog.search import Snapshot
from app.flights import City, RouteFlights, Ticket
from app.plan.assemble import assemble
from app.trip.brief import TripBrief
from tests.conftest import FakeFlights

CATALOG = load_catalog()
MOSCOW = City("MOW", "Москва", "Россия", 55.75, 37.62, "Москвы")
TODAY = date(2026, 10, 25)
FAMILY = TripBrief(
    month=11, nights_min=7, nights_max=7, adults=2, children=1, children_ages=[5], budget_level=2
)
COUPLE = TripBrief(month=11, nights_min=7, nights_max=7, adults=2, budget_level=2)


def snap(place_id: str, air: float = 23, sea: float | None = 23) -> Snapshot:
    climate = {"air_max": air, **({"sea_temp": sea} if sea is not None else {})}
    place = CATALOG.find(place_id)
    return Snapshot(place=place, climate={11: climate}, visa_rule="visa_free")


def flights(*tickets: tuple[str, str, int, int]) -> RouteFlights:
    """(departure ISO, destination IATA, price, minutes) per ticket."""
    found = sorted(
        (Ticket("XXX", to, "SU", "2134", at, price, 0, minutes, "/t") for at, to, price, minutes in tickets),
        key=lambda t: t.price,
    )
    return RouteFlights(cheapest=found[0], direct=found[0], fastest=found[0], by_day=tuple(found))


ANTALYA_TICKETS = FakeFlights(
    {
        "AYT": flights(("2026-11-06T09:40:00+03:00", "AYT", 18_000, 240)),
        "MOW": flights(("2026-11-13T15:00:00+03:00", "MOW", 17_000, 240)),
    }
)


def build(stops, brief=FAMILY, tickets=ANTALYA_TICKETS, **kwargs):
    return asyncio.run(assemble(stops, brief, tickets, MOSCOW, TODAY, **kwargs))


def test_should_follow_the_tickets_from_landing_to_the_flight_home():
    plan = build([snap("antalya")])

    stay = plan.stops[0]
    assert plan.dates_fixed
    assert (stay.check_in, stay.check_out) == (date(2026, 11, 6), date(2026, 11, 13))
    assert plan.days[0].date == date(2026, 11, 6) and plan.days[-1].date == date(2026, 11, 13)
    assert plan.days[0].items[0].kind == "flight"
    assert plan.days[-1].items[-1].kind == "flight"


def test_should_pick_a_hotel_that_takes_children():
    plan = build([snap("antalya")])

    hotel = plan.stops[0].pick.best.hotel
    assert not hotel.adults_only
    assert any("только для взрослых" in why for _, why in plan.stops[0].pick.excluded)


def test_should_check_the_landing_against_the_check_in():
    plan = build([snap("antalya")])

    titles = [c.title for c in plan.checks]
    assert "Прилёт 13:40, заселение с 14:00" in titles
    assert any(t.startswith("Выезд до 12:00, вылет 15:00") for t in titles)


def test_should_add_up_the_whole_bill_for_the_party():
    plan = build([snap("antalya")])

    stay = plan.stops[0]
    rides = stay.transfer_in.price_rub + stay.transfer_out.price_rub
    assert plan.costs.flights == (18_000 + 17_000) * 3  # a five-year-old needs a seat of their own
    assert plan.costs.total == plan.costs.flights + stay.pick.best.total_rub + rides
    assert plan.costs.per_person == round(plan.costs.total / 3)


def test_should_say_so_when_there_are_no_tickets_and_still_plan_the_stay():
    plan = build([snap("antalya")], tickets=FakeFlights())

    assert not plan.dates_fixed
    assert plan.stops[0].nights == 7
    assert plan.stops[0].check_in.month == 11
    assert any(
        c.level == "warn" and "Билетов" in c.title and "билетов в ноябре" in c.text for c in plan.checks
    )
    assert plan.days


def test_should_start_on_the_day_the_user_named_without_tickets():
    brief = COUPLE.model_copy(update={"date_from": date(2026, 11, 20), "date_to": date(2026, 11, 27)})

    plan = build([snap("antalya")], brief=brief, tickets=FakeFlights())

    assert (plan.stops[0].check_in, plan.stops[0].check_out) == (date(2026, 11, 20), date(2026, 11, 27))


def test_should_warn_when_the_trip_costs_more_than_the_budget():
    brief = COUPLE.model_copy(update={"budget_total": 50_000, "budget_currency": "RUB", "budget_level": None})

    plan = build([snap("antalya")], brief=brief)

    assert plan.costs.over_by == plan.costs.total - 50_000 > 0
    assert any(c.level == "warn" and c.kind == "budget" and "бюджет" in c.title.lower() for c in plan.checks)


def test_should_not_call_a_trip_in_budget_before_the_flights_are_counted():
    brief = COUPLE.model_copy(
        update={"budget_total": 300_000, "budget_currency": "RUB", "budget_level": None}
    )

    plan = build([snap("antalya")], brief=brief, tickets=FakeFlights())

    [budget] = [c for c in plan.checks if c.kind == "budget"]
    assert budget.level == "info" and "без перелётов" in budget.text


def test_should_name_the_wishes_it_could_not_meet():
    brief = COUPLE.model_copy(update={"wishes": ["с собакой", "чтобы был вид на вулкан"]})

    plan = build([snap("antalya")], brief=brief)

    assert plan.wishes_not_checked == ["чтобы был вид на вулкан"]
    hotel = plan.stops[0].pick.best.hotel
    assert hotel.pets or plan.unmet


def test_should_keep_the_hotel_the_user_asked_for():
    first = build([snap("antalya")], brief=COUPLE)
    other = first.stops[0].pick.alternatives[0].hotel

    plan = build([snap("antalya")], brief=COUPLE, prefer={"antalya": other.id})

    assert plan.stops[0].pick.best.hotel.id == other.id


def test_should_say_what_changed_since_the_last_plan():
    first = build([snap("antalya")], brief=COUPLE)
    other = first.stops[0].pick.alternatives[0].hotel

    plan = build([snap("antalya")], brief=COUPLE, prefer={"antalya": other.id}, previous=first.summary())

    assert any(other.name in change for change in plan.changes)
    assert not build([snap("antalya")], brief=COUPLE, previous=first.summary()).changes


def test_should_move_between_cities_by_land_on_the_check_out_day():
    tickets = FakeFlights(
        {
            "TBS": flights(("2026-11-06T08:00:00+03:00", "TBS", 15_000, 210)),
            "MOW": flights(("2026-11-14T16:00:00+04:00", "MOW", 16_000, 230)),
        }
    )
    brief = COUPLE.model_copy(update={"nights_min": 8, "nights_max": 8, "multi_city": True})

    plan = build([snap("tbilisi", sea=None), snap("yerevan", sea=None)], brief=brief, tickets=tickets)

    first, second = plan.stops
    assert first.check_out == second.check_in
    assert first.nights + second.nights == 8
    hop = next(d for d in plan.days if d.date == first.check_out)
    assert any(i.kind == "move" for i in hop.items)
    assert len([d for d in plan.days if d.date == first.check_out]) == 1
    assert plan.costs.ground > 0


def test_should_count_every_price_in_whole_roubles():
    plan = build([snap("antalya")])

    stay = plan.stops[0]
    prices = [
        stay.pick.best.night_rub,
        stay.pick.best.total_rub,
        stay.transfer_in.price_rub,
        plan.costs.total,
    ]
    prices += [r.night_rub for r in stay.pick.best.hotel.rates] + [stay.pick.best.hotel.early_check_in_rub]
    assert all(type(p) is int for p in prices)


def test_should_book_the_night_before_a_landing_after_midnight():
    tickets = FakeFlights(
        {
            "AYT": flights(("2026-11-05T23:30:00+03:00", "AYT", 18_000, 240)),  # lands 03:30 on 6 Nov
            "MOW": flights(("2026-11-13T15:00:00+03:00", "MOW", 17_000, 240)),
        }
    )

    plan = build([snap("antalya")], tickets=tickets)

    assert plan.dates_fixed
    assert (plan.stops[0].check_in, plan.stops[0].check_out) == (date(2026, 11, 5), date(2026, 11, 13))


def test_should_pay_each_night_once_and_list_a_red_eye_hop_once():
    tickets = FakeFlights(
        {
            "AER": flights(("2026-11-06T09:00:00+03:00", "AER", 8_000, 150)),
            "IST": flights(("2026-11-10T02:15:00+03:00", "IST", 12_000, 120)),  # leaves Sochi before midnight
            "MOW": flights(("2026-11-14T15:00:00+03:00", "MOW", 15_000, 240)),
        }
    )
    brief = COUPLE.model_copy(update={"nights_min": 8, "nights_max": 8, "multi_city": True})

    plan = build([snap("sochi"), snap("istanbul")], brief=brief, tickets=tickets)

    first, second = plan.stops
    assert plan.dates_fixed
    assert first.check_out == second.check_in == date(2026, 11, 9)
    hop = [i for d in plan.days for i in d.items if i.title == "Перелёт Сочи → Стамбул"]
    assert len(hop) == 1
    assert any(c.fix and c.fix["type"] == "late_check_out" for c in plan.checks)
