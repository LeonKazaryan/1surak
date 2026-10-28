"""Hotels for a stay: live ones with real rates and rooms (LiteAPI), else real ones from the directory and
OpenStreetMap with estimated offers, or the demo set where we have none.

HotelSource is what the trip assembly asks. With a LiteAPI key a place gets the hotels that have a room for the
party on those dates, at the provider's price (live.py). Otherwise, or when too few have one, a place with at least
MIN_REAL real hotels gets those with estimated offers; a place with fewer keeps the demo hotels, which are labelled
as such. `checked` adds what real sources say about the guest's wishes: the rooms on sale (amenities.py), then the
hotel's site and reviews for what they do not say (evidence.py).
"""

import logging
from collections.abc import Callable, Iterable
from dataclasses import replace
from datetime import date, time
from typing import Protocol

from app.catalog.catalog import Place
from app.hotels.amenities import need_of
from app.hotels.directory import Listed, directory, find, listed
from app.hotels.evidence import web_wishes
from app.hotels.live import LiveStays, area_text, offer_rate
from app.hotels.offers import EstimatedOffers, HotelOffers, Offer, StayQuery, priced_stars
from app.hotels.osm import merge_listings
from app.plan.hotels import Evidence, Hotel, Party, hotels_for, hundreds, rank_real

log = logging.getLogger(__name__)

MIN_REAL = 4


def real_hotel(h: Listed, offers: list[Offer], nights: int = 1) -> Hotel:
    rates = tuple(offer_rate(o, nights) for o in offers)
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


def _merged(ours: tuple[Evidence, ...], web: tuple[Evidence, ...], wishes: list[str]) -> tuple[Evidence, ...]:
    """One answer per wish, in the asked order: the rooms' data first, the web's only where the rooms say nothing."""
    by_wish = {e.wish: e for e in ours}
    for e in web:
        if e.wish not in by_wish or (by_wish[e.wish].verdict == "unknown" and e.verdict != "unknown"):
            by_wish[e.wish] = e
    return tuple(by_wish[w] for w in wishes if w in by_wish)


class HotelSource:
    def __init__(
        self,
        offers: HotelOffers | None = None,
        listing: Callable[[str], tuple[Listed, ...]] = listed,
        live: LiveHotels | None = None,
        evidence: WishChecker | None = None,
        stays: LiveStays | None = None,
    ):
        self.offers = offers or EstimatedOffers()
        self._listing = listing  # the directory; tests pass an empty one to get the demo hotels
        self._live = live
        self._evidence = evidence
        self._stays = stays  # hotels with live rates and rooms; None without a LiteAPI key

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
        user named are checked first. Live hotels answer on their rooms; the web takes what the rooms do not say
        (pets, quiet, good internet)."""
        if not (hotels and all(h.real for h in hotels)):
            return hotels
        live = self._stays is not None and all(h.provider for h in hotels)
        if live:
            hotels = await self._stays.checked(hotels, wishes, party, level, prefer)
        # the vocabulary's wishes are answered on the rooms; the web reads the rest, and pets when the rules are silent
        left = [w for w in web_wishes(wishes) if not live or (n := need_of(w)) is None or n.scope == "pets"]
        if not (self._evidence and left):
            return hotels
        order = sorted(rank_real(hotels, party, level), key=lambda h: h.id != prefer)
        found = await self._evidence.check(place, order, left)
        return [replace(h, evidence=_merged(h.evidence, found.get(h.id, ()), wishes)) for h in hotels]

    async def hotels(self, place: Place, check_in: date, nights: int, party: Party) -> list[Hotel]:
        if self._stays:
            try:
                if live := await self._stays.hotels(place, check_in, nights, party):
                    return live
            except Exception:  # the provider is down: the estimates still make a plan
                log.warning("Live hotels failed for %s", place.id, exc_info=True)
        found = list(await self.listing(place))
        if len(found) < MIN_REAL:
            return hotels_for(place, check_in.month)
        stay = StayQuery(place.id, check_in, nights, party.adults, party.children_ages)
        offers = await self.offers.offers(place, found, stay)
        hotels = [real_hotel(h, offers[h.id], nights) for h in found if offers.get(h.id)]
        return hotels if len(hotels) >= MIN_REAL else hotels_for(place, check_in.month)

    def warm(self, places: Iterable[Place]) -> None:
        """The hotels and rooms of the places on the cards start loading: one of them may be the trip."""
        if self._stays:
            self._stays.warm(places)

    @property
    def sandbox(self) -> bool:
        return bool(self._stays and self._stays.api.sandbox)


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
