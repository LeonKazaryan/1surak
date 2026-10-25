"""A day-by-day plan for one stay: real sights and food spots from the guide, paced for the party.

The first day starts after the ride from the airport, the last one ends before the ride back. Small
children get one sight a day and the beach; adults get a day trip out of town when the stay allows.
"""

from dataclasses import dataclass, field, replace
from datetime import date, datetime, time, timedelta
from typing import Literal

from app.plan.guide import Dish, Guide, Spot
from app.plan.hotels import Party
from app.trip.routes import km_between

ItemKind = Literal["sight", "trip", "food", "beach", "walk", "free", "flight", "transfer", "hotel", "move"]
LOGISTICS = ("flight", "transfer", "hotel", "move")
SLOTS = (
    ("morning", time(10)),
    ("lunch", time(13, 30)),
    ("afternoon", time(15, 30)),
    ("dinner", time(19, 30)),
)
LASTS = {
    "morning": timedelta(hours=2),
    "lunch": timedelta(hours=1, minutes=15),
    "afternoon": timedelta(hours=2, minutes=30),
    "dinner": timedelta(hours=1, minutes=30),
}
SETTLE = timedelta(minutes=30)  # after reaching the hotel, and before leaving it
LATEST_DINNER = time(22)
DINNER_OUT_EVERY = 3  # on all inclusive, every third dinner is at a local place in town
DAY_TRIP_FROM = 3  # full days a stay needs before one of them goes on a trip out of town


@dataclass(frozen=True)
class Item:
    kind: ItemKind
    title: str
    time: str | None = None
    note: str | None = None
    spot: Spot | None = None

    @property
    def spot_id(self) -> str | None:
        return self.spot.id if self.spot else None

    def view(self) -> dict:
        return {
            "kind": self.kind,
            "title": self.title,
            "time": self.time,
            "note": self.note,
            "spot": self.spot.view() if self.spot else None,
        }


@dataclass(frozen=True)
class Day:
    date: date
    title: str
    place_id: str
    items: list[Item] = field(default_factory=list)

    def view(self) -> dict:
        return {
            "date": self.date.isoformat(),
            "title": self.title,
            "place_id": self.place_id,
            "items": [i.view() for i in self.items],
        }


@dataclass(frozen=True)
class Stay:
    guide: Guide
    check_in: date
    check_out: date
    arrive: datetime | None  # local time the party reaches the hotel
    leave: datetime | None  # local time the party leaves for the airport or the next city
    hotel_at: tuple[float, float]
    sea: bool = False
    sea_warm: bool = False
    all_inclusive: bool = False


class _Menu:
    """Meals in turn: the guide's food spots, then local dishes to try, then simply a place nearby."""

    def __init__(self, guide: Guide, all_inclusive: bool):
        self.spots = list(guide.food)
        self.dishes: list[Dish] = list(guide.dishes)
        self.all_inclusive = all_inclusive
        self.dinners = 0

    def meal(self, slot: str) -> Item:
        name = "Обед" if slot == "lunch" else "Ужин"
        self.dinners += slot == "dinner"
        out = slot == "dinner" and self.dinners % DINNER_OUT_EVERY == 0
        if self.all_inclusive and not out:
            return Item("food", f"{name} в отеле", note="входит во «всё включено»")
        if self.spots:
            spot = self.spots.pop(0)
            return Item("food", f"{name}: {spot.name}", note=spot.summary, spot=spot)
        if self.dishes:
            dish = self.dishes.pop(0)
            return Item("food", f"{name}: попробуйте {dish.name}", note=dish.note or None)
        return Item("food", f"{name} рядом с отелем")


def _ordered(sights: list[Spot], at: tuple[float, float]) -> list[Spot]:
    def far(s: Spot) -> float:
        return km_between(*at, s.lat, s.lon) if s.lat is not None and s.lon is not None else 999

    return sorted(sights, key=lambda s: (not s.star, far(s)))


def _fits(start: time, slot: str, day: date, stay: Stay) -> bool:
    begins = datetime.combine(day, start)
    if stay.arrive and day == stay.check_in and begins < stay.arrive.replace(tzinfo=None) + SETTLE:
        return False
    return not (
        stay.leave
        and day == stay.check_out
        and begins + LASTS[slot] > stay.leave.replace(tzinfo=None) - SETTLE
    )


def _first_dinner(stay: Stay) -> time | None:
    """A late arrival still gets dinner, just later than usual."""
    if not stay.arrive:
        return None
    late = (stay.arrive + SETTLE).time()
    return late if SLOTS[-1][1] < late <= LATEST_DINNER else None


def plan_days(stay: Stay, party: Party) -> list[Day]:
    kids, small = bool(party.children_ages), party.small_kids
    dates = [stay.check_in + timedelta(days=i) for i in range((stay.check_out - stay.check_in).days + 1)]
    full = dates[1:-1]
    sights = _ordered([s for s in stay.guide.sights if s.type != "vicinity"], stay.hotel_at)
    trips = _ordered([s for s in stay.guide.sights if s.type == "vicinity"], stay.hotel_at)
    trip_day = full[len(full) // 2] if trips and not small and len(full) >= DAY_TRIP_FROM else None
    menu = _Menu(stay.guide, stay.all_inclusive)
    days = []
    for n, day in enumerate(dates):
        items: list[Item] = []
        if day == trip_day:
            trip = trips[0]
            items.append(Item("trip", f"Поездка на день: {trip.name}", "09:00", trip.summary, trip))
            items.append(replace(menu.meal("dinner"), time="19:30"))
            days.append(Day(day, f"Поездка: {trip.name}", stay.guide.place_id, items))
            continue
        for slot, start in SLOTS:
            if slot == "dinner" and day == stay.check_in and (late := _first_dinner(stay)):
                start = late
            elif not _fits(start, slot, day, stay):
                continue
            at = start.strftime("%H:%M")
            if slot in ("lunch", "dinner"):
                items.append(replace(menu.meal(slot), time=at))
            elif slot == "morning":
                items.append(_sight(sights, at) or _rest(stay, at, morning=True))
            elif stay.sea_warm and (kids or n % 2 == 0):
                items.append(Item("beach", "Пляж и море", at, "купаться и отдыхать"))
            elif not small and (sight := _sight(sights, at)):
                items.append(sight)
            else:
                items.append(_rest(stay, at, morning=False))
        days.append(Day(day, _title(day, dates, items), stay.guide.place_id, items))
    return days


def _sight(sights: list[Spot], at: str) -> Item | None:
    if not sights:
        return None
    spot = sights.pop(0)
    return Item("sight", spot.name, at, spot.summary, spot)


def _rest(stay: Stay, at: str, morning: bool) -> Item:
    if stay.sea_warm:
        return Item("beach", "Пляж и море", at, "купаться и отдыхать")
    if morning:
        return Item("walk", "Прогулка по городу", at, "без плана: улицы, набережная, кофе")
    return Item("free", "Свободное время", at, "отдых в отеле или прогулка")


def _title(day: date, dates: list[date], items: list[Item]) -> str:
    if day == dates[0]:
        return "Прилёт и первый вечер"
    if day == dates[-1]:
        return "Последнее утро и дорога домой"
    names = [i.title for i in items if i.kind == "sight"]
    if names:
        return " и ".join(names[:2])
    return "Море и отдых" if any(i.kind == "beach" for i in items) else "Свободный день"
