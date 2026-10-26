"""Airport to hotel and back: distance by the map, time by a declared estimate, price by the city's fare.

The price is the city's airport taxi fare found on the web, scaled to the hotel, or the country's kilometre
where no fare was found (app.plan.taxi). Never a quote: a figure to plan with.
"""

from dataclasses import dataclass
from typing import Literal

from app.catalog.catalog import Place
from app.plan.hotels import Hotel, Party, hundreds
from app.plan.places import PlaceInfo
from app.plan.taxi import TaxiFare, ride_price
from app.trip.routes import ROAD_DETOUR, km_between

CAR_SEATS = 4
BOAT_MINUTES = 45
BOAT_RUB_PER_PERSON = 12_000  # resort speedboats in the Maldives are sold per person


@dataclass(frozen=True)
class Transfer:
    mode: Literal["car", "boat"]
    km: int
    minutes: int
    price_rub: int  # the whole party, one way
    source: str | None = None  # the site the city's airport fare comes from; None: estimated by the kilometre

    def view(self) -> dict:
        return {
            "mode": self.mode,
            "km": self.km,
            "minutes": self.minutes,
            "price_rub": self.price_rub,
            "source": self.source,
        }


def _kmh(km: float) -> int:
    return 35 if km < 15 else 55 if km < 60 else 75


def transfer_to(
    hotel: Hotel,
    place: Place,
    info: PlaceInfo,
    party: Party,
    fare: TaxiFare | None = None,
    fare_rub: int | None = None,
) -> Transfer | None:
    """The ride for the whole party: as many cars as it fills, each at the city's fare for this distance."""
    if info.airport is None:
        return None
    if info.by_boat:
        return Transfer("boat", 0, BOAT_MINUTES, BOAT_RUB_PER_PERSON * party.guests)
    km = km_between(*info.airport, hotel.lat, hotel.lon) * ROAD_DETOUR
    to_centre = km_between(*info.airport, place.lat, place.lon) * ROAD_DETOUR
    minutes = round(10 + km / _kmh(km) * 60)
    cars = -(-party.guests // CAR_SEATS)
    price = ride_price(fare, fare_rub, km, to_centre, place.country.code)
    return Transfer("car", round(km), minutes, max(100, hundreds(price.rub)) * cars, price.source)
