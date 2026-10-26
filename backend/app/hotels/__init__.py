"""Hotels for a stay: real ones from the directory with cached offers, or the demo set where we have none.

HotelSource is what the trip assembly asks. A place with at least MIN_REAL hotels in the directory gets those,
each with its cheapest offers (estimated until a real provider is plugged in); a place with fewer keeps the
demo hotels, which are labelled as such.
"""

from collections.abc import Callable
from datetime import date, time

from app.catalog.catalog import Place
from app.hotels.directory import Listed, directory, find, listed
from app.hotels.offers import EstimatedOffers, HotelOffers, Offer, StayQuery, priced_stars
from app.plan.hotels import Hotel, Party, Rate, hotels_for, hundreds

MIN_REAL = 4


def area_text(centre_m: int) -> str:
    if centre_m <= 1500:
        return "в центре"
    km = centre_m / 1000
    return f"{km:.1f} км от центра".replace(".", ",") if km < 10 else f"{km:.0f} км от центра"


def real_hotel(h: Listed, offers: list[Offer]) -> Hotel:
    rates = tuple(
        Rate(o.meal, o.night_rub, o.free_cancel_days, o.pay_at_hotel, o.terms_known, o.kind == "estimate")
        for o in offers
    )
    night = min(r.night_rub for r in rates)
    return Hotel(
        id=h.id,
        place_id=h.place_id,
        name=h.name,
        stars=priced_stars(h),  # the chain's usual class when unmapped; stars_known keeps it off the card
        rating=None,
        reviews=None,
        area=area_text(h.centre_m),
        lat=h.lat,
        lon=h.lon,
        beach_m=None,
        kids_club=False,
        family_rooms=False,
        adults_only=False,
        pets=False,
        pool=False,
        spa=False,
        reception_24h=False,
        check_in=time(14),  # the usual times; the hotel's own come with a real offer
        check_out=time(12),
        early_check_in_rub=hundreds(night * 0.5),
        late_check_out_rub=hundreds(night * 0.5),
        rates=rates,
        real=True,
        stars_known=h.stars is not None,
        photo=h.photo,
        source_url=h.source_url,
        centre_m=h.centre_m,
    )


class HotelSource:
    def __init__(
        self, offers: HotelOffers | None = None, listing: Callable[[str], tuple[Listed, ...]] = listed
    ):
        self.offers = offers or EstimatedOffers()
        self._listing = listing  # the directory; tests pass an empty one to get the demo hotels

    async def hotels(self, place: Place, check_in: date, nights: int, party: Party) -> list[Hotel]:
        found = list(self._listing(place.id))
        if len(found) < MIN_REAL:
            return hotels_for(place, check_in.month)
        stay = StayQuery(place.id, check_in, nights, party.adults, party.children_ages)
        offers = await self.offers.offers(place, found, stay)
        hotels = [real_hotel(h, offers[h.id]) for h in found if offers.get(h.id)]
        return hotels if len(hotels) >= MIN_REAL else hotels_for(place, check_in.month)


__all__ = [
    "MIN_REAL",
    "EstimatedOffers",
    "HotelOffers",
    "HotelSource",
    "Listed",
    "Offer",
    "StayQuery",
    "directory",
    "find",
    "listed",
    "real_hotel",
]
