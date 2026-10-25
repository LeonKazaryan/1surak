"""Do the pieces of the trip meet: the landing, the ride and the check-in; the check-out and the flight home.

Every check is plain arithmetic on local times, so a 23:40 landing with a 23:00 reception is caught in code.
"""

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Literal

from app.flights import Ticket
from app.plan.hotels import Hotel
from app.plan.places import PlaceInfo

NIGHT_ENDS = timedelta(hours=6)  # reach the hotel before 6 am and you need the room from the night before
EARLY_WAIT = timedelta(hours=1, minutes=30)  # a shorter wait for the room is not worth a word
AIRPORT_BEFORE = {
    True: timedelta(hours=2, minutes=30),
    False: timedelta(hours=1, minutes=30),
}  # abroad or not
LATE_RECEPTION = 23  # without a 24-hour reception, arriving after this hour needs a word with the hotel
BREAKFAST_DONE = time(8)


@dataclass(frozen=True)
class Check:
    level: Literal["ok", "info", "warn"]
    title: str
    text: str
    fix: dict | None = None
    kind: Literal["timing", "tickets", "move", "budget"] = "timing"

    def view(self) -> dict:
        return {
            "level": self.level,
            "title": self.title,
            "text": self.text,
            "fix": self.fix,
            "kind": self.kind,
        }


def _hm(moment: datetime) -> str:
    return moment.strftime("%H:%M")


def at_hotel(landing: Ticket, info: PlaceInfo, transfer_minutes: int) -> datetime | None:
    arrives = landing.arrives
    return info.local(arrives) + timedelta(minutes=transfer_minutes) if arrives else None


def arrival_checks(landing: Ticket, hotel: Hotel, info: PlaceInfo, transfer_minutes: int) -> list[Check]:
    reached = at_hotel(landing, info, transfer_minutes)
    if reached is None:
        return []
    lands = _hm(info.local(landing.arrives))
    check_in = datetime.combine(reached.date(), hotel.check_in, reached.tzinfo)
    title = f"Прилёт {lands}, заселение с {hotel.check_in:%H:%M}"
    if reached.time() < time(NIGHT_ENDS.seconds // 3600):
        if hotel.reception_24h:
            return [
                Check(
                    "info",
                    title,
                    f"В отеле вы будете ночью, около {_hm(reached)}. Номер бронирую с вечера накануне, ресепшен работает круглосуточно.",
                )
            ]
        return [
            Check(
                "warn",
                title,
                f"В отеле вы будете около {_hm(reached)}, а ресепшен ночью закрыт: предупредим отель о позднем заезде.",
            )
        ]
    if reached.hour >= LATE_RECEPTION and not hotel.reception_24h:
        return [
            Check(
                "warn",
                title,
                f"В отеле вы будете в {_hm(reached)}, ресепшен до {LATE_RECEPTION}:00: предупредим о позднем заезде.",
            )
        ]
    wait = check_in - reached
    if wait >= EARLY_WAIT:
        fix = _fix("early_check_in", f"Ранний заезд в «{hotel.name}»", hotel, hotel.early_check_in_rub)
        text = f"В отеле вы будете около {_hm(reached)}, а заселение с {hotel.check_in:%H:%M}. Можно взять ранний заезд или оставить вещи и сразу пойти гулять."
        return [Check("warn", title, text, fix)]
    return [Check("ok", title, f"В отеле около {_hm(reached)}, как раз к заселению.")]


def _fix(kind: str, label: str, hotel: Hotel, price_rub: int) -> dict:
    """An extra the user can buy at checkout; the id names the hotel, so each stop gets its own."""
    return {"id": f"{kind}:{hotel.id}", "type": kind, "label": label, "price_rub": price_rub}


def keeps_room_to_flight(go: datetime, flight: datetime, last: bool) -> bool:
    """A flight home after midnight keeps the room that night; mid-trip the next hotel already has it."""
    return last and go.date() < flight.date()


def departure_checks(
    back: Ticket, hotel: Hotel, info: PlaceInfo, transfer_minutes: int, abroad: bool, last: bool = True
) -> list[Check]:
    leaves = back.departs
    if leaves is None:
        return []
    flight = info.local(leaves)
    go = flight - AIRPORT_BEFORE[abroad] - timedelta(minutes=transfer_minutes)
    check_out = datetime.combine(go.date(), hotel.check_out, go.tzinfo)
    title = f"Выезд до {hotel.check_out:%H:%M}, вылет {_hm(flight)}"
    if keeps_room_to_flight(go, flight, last):
        return [
            Check("ok", title, f"Ночь перед вылетом уже в брони: номер ваш до выезда в аэропорт в {_hm(go)}.")
        ]
    if go.time() < BREAKFAST_DONE:
        return [
            Check(
                "info", title, f"Выезжать в аэропорт в {_hm(go)}: попросим завтрак с собой и такси заранее."
            )
        ]
    if go - check_out >= timedelta(hours=1):
        fix = _fix("late_check_out", f"Поздний выезд из «{hotel.name}»", hotel, hotel.late_check_out_rub)
        text = f"Выезд из отеля в {hotel.check_out:%H:%M}, а в аэропорт ехать в {_hm(go)}. Можно взять поздний выезд или оставить вещи в камере хранения."
        return [Check("warn", title, text, fix)]
    return [Check("ok", title, f"После завтрака и выезда как раз время ехать в аэропорт, около {_hm(go)}.")]
