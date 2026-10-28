"""Hotel offers: what a room costs for a stay. A provider gives them; the cache (cache.py) keeps them.

Today the only provider is EstimatedOffers: a declared formula on stars, the place's price level and the
season, calibrated like the demo hotels. Its offers say `kind="estimate"` and `terms_known=False`, so the
plan shows «цена ориентировочная, условия уточним» and never invents a meal plan or a cancellation rule.
A real provider returns `kind="real"` offers through the same Protocol: LiteAPI does (liteapi.py), with the room
it sells and the exact price of the stay for the whole party.
"""

import hashlib
from dataclasses import asdict, dataclass
from datetime import date
from typing import Literal, Protocol

from app.catalog.catalog import Place
from app.hotels.directory import Listed
from app.plan.hotels import MEAL_FACTOR, NIGHT_BASE_RUB, STAR_FACTOR, hundreds, season_factor

OfferKind = Literal["real", "estimate"]
ESTIMATE_SOURCE = "оценка 1surak"
LOW_STARS = {1: 0.6, 2: 0.8}  # below the demo hotels' three stars


@dataclass(frozen=True)
class StayQuery:
    """One stay to price: the same key for every hotel of the place, as a booking site searches a region."""

    place_id: str
    check_in: date
    nights: int
    adults: int = 2
    children: tuple[int, ...] = ()
    nationality: str = ""  # a live provider prices by the guest's passport

    @property
    def key(self) -> str:
        kids = ",".join(map(str, self.children))
        key = f"{self.check_in.isoformat()}:{self.nights}:{self.adults}:{kids}"
        return f"{key}:{self.nationality}" if self.nationality else key


@dataclass(frozen=True)
class Offer:
    hotel_id: str
    meal: str  # room_only | breakfast | half_board | all_inclusive
    night_rub: int  # a room for two, one night
    free_cancel_days: int | None = None
    pay_at_hotel: bool = False
    terms_known: bool = False  # the meal, cancellation and payment rules are the provider's, not ours
    kind: OfferKind = "estimate"
    source: str = ESTIMATE_SOURCE
    # a live offer's room and its whole stay for the whole party (night_rub is then the party's night)
    room: str | None = None
    room_id: str | None = None
    stay_rub: int | None = None
    cancel_until: str | None = None  # ISO date: free to cancel until then

    def as_dict(self) -> dict:
        return asdict(self)


class HotelOffers(Protocol):
    async def offers(self, place: Place, hotels: list[Listed], stay: StayQuery) -> dict[str, list[Offer]]:
        """Offers per hotel id. A hotel with no offer is left out; a failure raises, and is not cached."""
        ...


# A chain's usual class, for pricing a hotel whose stars nobody mapped. Only the estimate uses it: the card
# never shows these as the hotel's stars. Longer names first, so «Hilton Garden Inn» is not read as «Hilton».
CHAIN_STARS: tuple[tuple[str, int], ...] = (
    ("hostel", 1),
    ("хостел", 1),
    ("guest house", 2),
    ("гостевой дом", 2),
    ("мини-отель", 2),
    ("mini hotel", 2),
    ("ibis budget", 2),
    ("ibis styles", 3),
    ("ibis", 3),
    ("hampton", 3),
    ("best western", 3),
    ("holiday inn express", 3),
    ("hilton garden inn", 4),
    ("courtyard", 4),
    ("four points", 4),
    ("holiday inn", 4),
    ("novotel", 4),
    ("mercure", 4),
    ("doubletree", 4),
    ("radisson", 4),
    ("crowne plaza", 4),
    ("renaissance", 4),
    ("ramada", 4),
    ("wyndham", 4),
    ("park inn", 4),
    ("hyatt regency", 5),
    ("park hyatt", 5),
    ("grand hyatt", 5),
    ("hyatt", 4),
    ("sheraton", 4),
    ("marriott", 5),
    ("hilton", 5),
    ("swissotel", 5),
    ("intercontinental", 5),
    ("pullman", 5),
    ("sofitel", 5),
    ("westin", 5),
    ("movenpick", 5),
    ("mövenpick", 5),
    ("kempinski", 5),
    ("fairmont", 5),
    ("ritz", 5),
    ("four seasons", 5),
    ("st. regis", 5),
    ("mandarin oriental", 5),
    ("shangri-la", 5),
    ("jumeirah", 5),
    ("rixos", 5),
    ("waldorf", 5),
    ("raffles", 5),
    ("rosewood", 5),
    ("armani", 5),
    ("bulgari", 5),
)


def priced_stars(hotel: Listed) -> int:
    """The stars the estimate prices at: the mapped ones, else the chain's usual class, else three."""
    if hotel.stars:
        return hotel.stars
    name = hotel.name.casefold()
    return next((stars for chain, stars in CHAIN_STARS if chain in name), 3)


def _jitter(hotel_id: str) -> float:
    """The same hotel is always a bit dearer or cheaper than its neighbours: 0.85 to 1.2."""
    digest = hashlib.sha256(hotel_id.encode()).digest()
    return 0.85 + 0.35 * int.from_bytes(digest[:4], "big") / 2**32


class EstimatedOffers:
    """What a room usually costs there: the demo hotels' calibrated formula, applied to real hotels."""

    async def offers(self, place: Place, hotels: list[Listed], stay: StayQuery) -> dict[str, list[Offer]]:
        season = season_factor(place, stay.check_in.month)
        found = {}
        for h in hotels:
            stars = STAR_FACTOR.get(priced_stars(h)) or LOW_STARS.get(priced_stars(h), 1.0)
            central = 1.1 if h.centre_m <= 1500 else 1.0
            base = NIGHT_BASE_RUB[place.price_level] * stars * season * central * _jitter(h.id)
            found[h.id] = [
                Offer(h.id, meal, hundreds(base * MEAL_FACTOR[meal])) for meal in ("room_only", "breakfast")
            ]
        return found
