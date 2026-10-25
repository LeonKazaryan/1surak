"""Airport to hotel and back: distance by the map, time and price by a declared estimate, never a quote."""

from dataclasses import dataclass
from typing import Literal

from app.catalog.catalog import Place
from app.plan.hotels import Hotel, Party, hundreds
from app.plan.places import PlaceInfo
from app.trip.routes import ROAD_DETOUR, km_between

# A taxi or private car for the whole party, by the catalogue price level of the place.
RUB_PER_KM = {1: 30, 2: 45, 3: 70}
MIN_RIDE_RUB = 800
CAR_SEATS = 4
BOAT_MINUTES = 45
BOAT_RUB_PER_PERSON = 12_000  # resort speedboats in the Maldives are sold per person


@dataclass(frozen=True)
class Transfer:
    mode: Literal["car", "boat"]
    km: int
    minutes: int
    price_rub: int  # the whole party, one way

    def view(self) -> dict:
        return {"mode": self.mode, "km": self.km, "minutes": self.minutes, "price_rub": self.price_rub}


def _kmh(km: float) -> int:
    return 35 if km < 15 else 55 if km < 60 else 75


def transfer_to(hotel: Hotel, place: Place, info: PlaceInfo, party: Party) -> Transfer | None:
    if info.airport is None:
        return None
    if info.by_boat:
        return Transfer("boat", 0, BOAT_MINUTES, BOAT_RUB_PER_PERSON * party.guests)
    km = km_between(*info.airport, hotel.lat, hotel.lon) * ROAD_DETOUR
    minutes = round(10 + km / _kmh(km) * 60)
    cars = -(-party.guests // CAR_SEATS)
    price = max(MIN_RIDE_RUB, hundreds(km * RUB_PER_KM[place.price_level])) * cars
    return Transfer("car", round(km), minutes, price)
