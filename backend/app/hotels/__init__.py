"""Hotels for a stay: real ones from the directory and OpenStreetMap with cached offers, or the demo set where
we have none.

HotelSource is what the trip assembly asks. A place with at least MIN_REAL real hotels gets those, each with its
cheapest offers (estimated until a real provider is plugged in); a place with fewer keeps the demo hotels, which
are labelled as such. `checked` adds what real sources say about the guest's wishes (evidence.py).
"""

from collections.abc import Callable
from dataclasses import replace
from datetime import date, time
from typing import Protocol

from app.catalog.catalog import Place
from app.hotels.directory import Listed, directory, find, listed
from app.hotels.offers import EstimatedOffers, HotelOffers, Offer, StayQuery, priced_stars
from app.hotels.osm import merge_listings
from app.plan.hotels import Evidence, Hotel, Party, Rate, hotels_for, hundreds, rank_real

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
        website=h.website,
        tags=h.tags,
    )


class LiveHotels(Protocol):
    async def around(self, place: Place) -> list[Listed]: ...


class WishChecker(Protocol):
    async def check(
        self, place: Place, hotels: list[Hotel], wishes: list[str]
    ) -> dict[str, tuple[Evidence, ...]]: ...


class HotelSource:
    def __init__(
        self,
        offers: HotelOffers | None = None,
        listing: Callable[[str], tuple[Listed, ...]] = listed,
        live: LiveHotels | None = None,
        evidence: WishChecker | None = None,
    ):
        self.offers = offers or EstimatedOffers()
        self._listing = listing  # the directory; tests pass an empty one to get the demo hotels
        self._live = live
        self._evidence = evidence

    async def listing(self, place: Place) -> tuple[Listed, ...]:
        """The seed's hotels completed with OpenStreetMap's, plus the ones only OpenStreetMap has."""
        seed = self._listing(place.id)
        return merge_listings(seed, await self._live.around(place)) if self._live else seed

    async def checked(
        self,
        place: Place,
        hotels: list[Hotel],
        wishes: list[str],
        party: Party,
        level: int | None,
        prefer: str | None = None,
    ) -> list[Hotel]:
        """The same hotels with what real sources say about the wishes: the best candidates and the hotel the
        user named are checked first."""
        if not (self._evidence and wishes and hotels and all(h.real for h in hotels)):
            return hotels
        order = sorted(rank_real(hotels, party, level), key=lambda h: h.id != prefer)
        found = await self._evidence.check(place, order, wishes)
        return [replace(h, evidence=found.get(h.id, ())) for h in hotels]

    async def hotels(self, place: Place, check_in: date, nights: int, party: Party) -> list[Hotel]:
        found = list(await self.listing(place))
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
