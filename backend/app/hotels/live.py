"""Hotels with live offers: LiteAPI's hotels around the place, priced for the stay, the best ones with their rooms.

`hotels` answers from the caches when it can: the hotels of a place for a month, the rates of a stay for hours.
`checked` reads the rooms of the hotels worth showing (cached for a month) and answers the guest's wishes on the
very rooms on sale (amenities.py): a hotel whose rooms say no is ruled out, a hotel whose rooms say yes is sold
with that room.
"""

import re
from collections.abc import Callable, Iterable
from dataclasses import replace
from datetime import date, time

from app.catalog.catalog import Place
from app.hotels.amenities import judge, reads_rooms
from app.hotels.cache import CachedOffers
from app.hotels.liteapi import Around, Details, LiteApi, to_price
from app.hotels.offers import Offer, StayQuery
from app.hotels.osm import metres
from app.plan.hotels import LITEAPI, Hotel, Party, Rate, hundreds, rank_real

MIN_LIVE = 2  # fewer priced hotels than this and the place keeps its other hotels
DETAILED = 8  # the hotels whose rooms are read for the card
# a bath or a pool is only in a hotel's own page: more hotels are read to find the ones that have it
DETAILED_FOR_WISHES = 20
DETAILS_WAIT_S = 6.0  # a hotel whose rooms take longer is shown without them; they are cached for next time
WARMED = 10  # read while the cards are looked at, a few a second, so a plan seldom waits for one
ADULTS_ONLY_NAME = re.compile(r"adults?[\s-]only|только для взрослых", re.IGNORECASE)
CENTRE_M = 1500


def area_text(centre_m: int) -> str:
    if centre_m <= CENTRE_M:
        return "в центре"
    km = centre_m / 1000
    return f"{km:.1f} км от центра".replace(".", ",") if km < 10 else f"{km:.0f} км от центра"


def offer_rate(o: Offer, nights: int) -> Rate:
    return Rate(
        o.meal,
        o.night_rub,
        o.free_cancel_days,
        o.pay_at_hotel,
        o.terms_known,
        o.kind == "estimate",
        room=o.room,
        room_id=o.room_id,
        for_party=o.stay_rub is not None,
        stay_rub=o.stay_rub,
        stay_nights=nights if o.stay_rub is not None else None,
        cancel_until=date.fromisoformat(o.cancel_until) if o.cancel_until else None,
    )


def live_hotel(place: Place, a: Around, offers: list[Offer], nights: int, sandbox: bool) -> Hotel:
    rates = tuple(offer_rate(o, nights) for o in offers)
    night = min(r.night_rub for r in rates)
    centre = metres(place.lat, place.lon, a.lat, a.lon)
    return Hotel(
        id=f"{place.id}-{a.id}",
        place_id=place.id,
        name=a.name,
        stars=a.stars or 3,  # priced as a three; stars_known keeps it off the card
        rating=a.rating,
        reviews=a.reviews,
        area=area_text(centre),
        lat=a.lat,
        lon=a.lon,
        beach_m=None,
        kids_club=False,
        family_rooms=False,
        adults_only=bool(ADULTS_ONLY_NAME.search(a.name)),
        pets=False,
        pool=False,
        spa=False,
        reception_24h=False,
        check_in=time(14),  # the usual times until the hotel's own are read
        check_out=time(12),
        early_check_in_rub=hundreds(night * 0.5),
        late_check_out_rub=hundreds(night * 0.5),
        rates=rates,
        real=True,
        stars_known=a.stars is not None,
        centre_m=centre,
        provider=LITEAPI,
        provider_id=a.id,
        sandbox=sandbox,
        gallery=(a.photo,) if a.photo else (),
    )


def _has(facilities: Iterable[str], *names: str) -> bool:
    lowered = {f.casefold() for f in facilities}
    return any(n in lowered for n in names)


def with_details(h: Hotel, d: Details) -> Hotel:
    """The hotel with what its page says: photos, rooms, its own check-in times, what guests rate it for."""
    clock = {k: time.fromisoformat(v) for k, v in (("in", d.check_in), ("out", d.check_out)) if v}
    return replace(
        h,
        gallery=d.photos or h.gallery,
        rooms={r.id: r for r in d.rooms},
        scores=d.scores,
        check_in=clock.get("in", h.check_in),
        check_out=clock.get("out", h.check_out),
        website=d.website or h.website,
        kids_club=_has(d.facilities, "kids' club", "kids club", "children's club"),
        family_rooms=_has(d.facilities, "family rooms"),
        adults_only=h.adults_only or _has(d.facilities, "adult only", "adults only"),
        pets=d.pets is True,
        pool=any("pool" in f.casefold() and "nearby" not in f.casefold() for f in d.facilities),
        spa=_has(d.facilities, "spa/wellness center", "spa", "full-service spa", "sauna"),
        reception_24h=_has(d.facilities, "24-hour front desk"),
    )


class LiveStays:
    def __init__(self, api: LiteApi, offers: CachedOffers, nationality: Callable[[], str]):
        self.api = api
        self.offers = offers
        self._nationality = nationality

    async def hotels(self, place: Place, check_in: date, nights: int, party: Party) -> list[Hotel]:
        """The place's hotels with a room for the party on these dates; [] when too few have one."""
        priced = to_price(await self.api.around(place))
        if len(priced) < MIN_LIVE:
            return []
        stay = StayQuery(place.id, check_in, nights, party.adults, party.children_ages, self._nationality())
        offers = await self.offers.offers(place, priced, stay)
        found = [
            live_hotel(place, a, offers[a.id], nights, self.api.sandbox) for a in priced if offers.get(a.id)
        ]
        if len(found) < MIN_LIVE:
            return []
        # rooms read on an earlier search come with no wait
        return [with_details(h, d) if (d := self.api.known(h.provider_id)) else h for h in found]

    async def checked(
        self, hotels: list[Hotel], wishes: list[str], party: Party, level: int | None, prefer: str | None
    ) -> list[Hotel]:
        """The hotels with their rooms read and the wishes answered on them: the hotels the rates already show to
        fit (a «Studio Ocean View» needs no more reading), then the best by stars, rating and price."""
        fits = {h.id: sum(e.verdict == "yes" for e in judge(wishes, h.rates, None)[0]) for h in hotels}
        ranked = sorted(rank_real(hotels, party, level), key=lambda h: -fits[h.id])
        top = [h for h in hotels if h.id == prefer] + ranked[
            : DETAILED_FOR_WISHES if reads_rooms(wishes) else DETAILED
        ]
        read = await self.api.details([h.provider_id for h in top if h.provider_id], DETAILS_WAIT_S)
        checked = []
        for h in hotels:
            if details := read.get(h.provider_id or "") or self.api.known(h.provider_id):
                h = with_details(h, details)
            if wishes:
                evidence, rates = judge(wishes, h.rates, details)
                h = replace(h, evidence=evidence, rates=rates)
            checked.append(h)
        return checked

    def warm(self, places: Iterable[Place]) -> None:
        self.api.warm(places, WARMED)

    async def settle(self) -> None:
        await self.api.settle()
        await self.offers.settle()
