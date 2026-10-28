"""LiteAPI (Nuitee): hotels around a place with live room rates, and each hotel's rooms, photos and rules.

Three calls, each kept for as long as its answer holds:
- the hotels around a place (`/data/hotels`): a month, in the lookups table;
- one hotel's rooms, photos, facilities and rules (`/data/hotel`): a month, trimmed to what the plan uses;
- the rates of a stay (`/hotels/rates`): through CachedOffers like any offers, hours to a day by the check-in.
A rate names its room (`mappedRoomId`), so a wish is checked on the very room that is sold: its view, its bath.
Photos are LiteAPI's own (static.cupid.travel); the third-party failover links it also sends are never kept.
A sandbox key (`sand_…`) is answered with test rates, and the plan says so.
"""

import asyncio
import logging
import math
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta

import httpx

from app.catalog.catalog import Place
from app.flights.freshness import RateLimit
from app.hotels.offers import Offer, StayQuery
from app.lookups import Lookups, LookupStore
from app.plan.hotels import LITEAPI, ROOM_SIZE

log = logging.getLogger(__name__)

BASE_URL = "https://api.liteapi.travel/v3.0"
PHOTO_HOST = "https://static.cupid.travel/"
RADIUS_M = 8000  # the town and its resort strip, not the whole region
LISTED = 60
PRICED = 40  # of the listed hotels, the most reviewed of every class are priced for a stay
SUPPLIER_WAIT_S = 6  # how long LiteAPI waits for its suppliers' rates
TIMEOUT_S = 15.0
KEPT_FOR = timedelta(days=30)  # the hotels of a place and a hotel's rooms hardly change in a month
MISSED_FOR = timedelta(days=1)
HOTEL_PHOTOS = 12
ROOM_PHOTOS = 8
OFFERS_PER_HOTEL = 12
BUSY_WAITS_S = (1.0, 2.0, 0.0)  # «too many requests»: asked again after these pauses, the last answer stands
MAX_BUSY_WAIT_S = 5.0
NO_AVAILABILITY = 2001  # LiteAPI's error code for «no rooms that night»: an answer, not a failure
MEALS = {
    "RO": "room_only",
    "BB": "breakfast",
    "BI": "breakfast",
    "HB": "half_board",
    "FB": "full_board",
    "AI": "all_inclusive",
    "UAI": "all_inclusive",
}
MEAL_WORDS = (
    ("all inclusive", "all_inclusive"),
    ("full board", "full_board"),
    ("half board", "half_board"),
    ("breakfast", "breakfast"),
)
SKIPPED_SCORES = {"Overall Experience"}


@dataclass(frozen=True)
class Around:
    """A hotel near the place, as the list gives it."""

    id: str
    name: str
    stars: int | None
    rating: float | None  # out of 10; None until guests rate it
    reviews: int | None
    lat: float
    lon: float
    photo: str | None


@dataclass(frozen=True)
class Room:
    id: str
    name: str
    size_m2: int | None
    beds: tuple[tuple[int, str], ...]  # (how many, what kind): (2, "Twin bed")
    views: tuple[str, ...]
    amenities: tuple[str, ...]
    photos: tuple[str, ...]


@dataclass(frozen=True)
class Details:
    id: str
    photos: tuple[str, ...]  # the hotel's, its main photo first
    facilities: tuple[str, ...]
    rooms: tuple[Room, ...]
    pets: bool | None  # the hotel's own rule; None: it does not say
    check_in: str | None  # «15:00»
    check_out: str | None
    scores: tuple[tuple[str, float], ...]  # what guests rate it for: ("Location", 9.07)
    website: str | None = None


def _photo(url: str | None) -> str | None:
    return url if isinstance(url, str) and url.startswith(PHOTO_HOST) else None


def _number(value) -> float | None:
    return float(value) if isinstance(value, int | float) and value > 0 else None


def around_from(rows: list[dict]) -> tuple[Around, ...]:
    found = []
    for row in rows:
        if not row.get("id") or not (row.get("name") or "").strip():
            continue
        if row.get("latitude") is None or row.get("longitude") is None:
            continue
        rating = _number(row.get("rating"))
        found.append(
            Around(
                id=row["id"],
                name=row["name"].strip(),
                stars=round(row["stars"]) if _number(row.get("stars")) else None,
                rating=rating,
                reviews=int(row["reviewCount"]) if rating and _number(row.get("reviewCount")) else None,
                lat=float(row["latitude"]),
                lon=float(row["longitude"]),
                photo=_photo(row.get("main_photo")),
            )
        )
    return tuple(found)


def _clock(value: str | None) -> str | None:
    """«15:00» or «03:00 PM» as «15:00»."""
    if not value:
        return None
    for pattern in ("%H:%M", "%I:%M %p", "%I %p"):
        try:
            return datetime.strptime(value.strip().upper(), pattern).strftime("%H:%M")
        except ValueError:
            continue
    return None


def _pets(data: dict) -> bool | None:
    """Only a rule the hotel states: LiteAPI's petsAllowed is false by default, so its false says nothing."""
    allowed = ((data.get("policyAttributes") or {}).get("pets") or {}).get("allowed")
    if isinstance(allowed, bool):
        return allowed
    if data.get("petsAllowed") is True:
        return True
    facilities = {f.casefold() for f in data.get("hotelFacilities") or []}
    if facilities & {"pets allowed", "pet friendly", "pets allowed on request"}:
        return True
    if facilities & {"pets not allowed", "no pets allowed"}:
        return False
    return None


def _room(row: dict) -> Room:
    photos = sorted(row.get("photos") or [], key=lambda p: not p.get("mainPhoto"))
    size = _number(row.get("roomSizeSquare"))
    if size and (row.get("roomSizeUnit") or "").casefold() in ("sqft", "ft2", "square feet"):
        size *= 0.0929
    return Room(
        id=str(row["id"]),
        name=(row.get("roomName") or "").strip(),
        size_m2=round(size) if size else None,
        beds=tuple(
            (int(b.get("quantity") or 1), b["bedType"].strip())
            for b in row.get("bedTypes") or []
            if (b.get("bedType") or "").strip()
        ),
        views=tuple(v["view"] for v in row.get("views") or [] if v.get("view")),
        amenities=tuple(a["name"] for a in row.get("roomAmenities") or [] if a.get("name")),
        photos=tuple(
            dict.fromkeys(u for p in photos if (u := _photo(p.get("hd_url")) or _photo(p.get("url"))))
        )[:ROOM_PHOTOS],
    )


def details_from(data: dict) -> Details:
    images = sorted(data.get("hotelImages") or [], key=lambda i: not i.get("defaultImage"))
    photos = [_photo(data.get("main_photo"))] + [
        _photo(i.get("urlHd")) or _photo(i.get("url")) for i in images
    ]
    policy = data.get("policyAttributes") or {}
    times = data.get("checkinCheckoutTimes") or {}
    sentiment = data.get("sentiment_analysis") or {}
    return Details(
        id=data["id"],
        photos=tuple(dict.fromkeys(p for p in photos if p))[:HOTEL_PHOTOS],
        facilities=tuple(f for f in data.get("hotelFacilities") or [] if isinstance(f, str)),
        rooms=tuple(_room(r) for r in data.get("rooms") or [] if r.get("id") is not None),
        pets=_pets(data),
        check_in=_clock((policy.get("checkIn") or {}).get("from")) or _clock(times.get("checkin_start")),
        check_out=_clock((policy.get("checkOut") or {}).get("until")) or _clock(times.get("checkout")),
        scores=tuple(
            (c["name"], float(c["rating"]))
            for c in sentiment.get("categories") or []
            if c.get("name") and _number(c.get("rating")) and c["name"] not in SKIPPED_SCORES
        ),
        website=data.get("website") or None,
    )


def _meal(rate: dict) -> str:
    if code := MEALS.get((rate.get("boardType") or "").upper()):
        return code
    name = (rate.get("boardName") or "").casefold()
    return next((meal for words, meal in MEAL_WORDS if words in name), "room_only")


def _amount(prices) -> float:
    """The first amount of LiteAPI's price list (or a single price): RUB, as the rates were asked in."""
    price = prices[0] if isinstance(prices, list) and prices else prices
    return float(price.get("amount") or 0) if isinstance(price, dict) else 0.0


def _free_until(rates: list[dict], today: date) -> date | None:
    """The last day every room of the offer can be cancelled free: None when one of them cannot, or when the
    deadline is not stated or already passed."""
    days = []
    for rate in rates:
        policy = rate.get("cancellationPolicies") or {}
        if policy.get("refundableTag") != "RFN":
            return None
        deadlines = [
            datetime.fromisoformat(info["cancelTime"]).date()
            for info in policy.get("cancelPolicyInfos") or []
            if info.get("cancelTime") and _number(info.get("amount"))
        ]
        if not deadlines:
            return None
        days.append(min(deadlines))
    until = min(days, default=None)
    return until if until and until >= today else None


def offers_from(rows: list[dict], stay: StayQuery, today: date) -> dict[str, list[Offer]]:
    """One offer per room type: its room, meal plan and refund, and the whole stay for every room of the party.
    Of the same room sold twice, the cheaper offer is kept."""
    found: dict[str, list[Offer]] = {}
    for hotel in rows:
        offers: dict[tuple, Offer] = {}
        for room_type in hotel.get("roomTypes") or []:
            rates = room_type.get("rates") or []
            if not rates:
                continue
            total = _amount(room_type.get("offerRetailRate")) or sum(
                _amount((r.get("retailRate") or {}).get("total")) for r in rates
            )
            if total <= 0:
                continue
            first = rates[0]
            until = _free_until(rates, today)
            room_id = str(first["mappedRoomId"]) if first.get("mappedRoomId") else None
            offer = Offer(
                hotel_id=hotel["hotelId"],
                meal=_meal(first),
                night_rub=round(total / stay.nights),
                free_cancel_days=(stay.check_in - until).days if until else None,
                pay_at_hotel="PROPERTY_PAY" in (first.get("paymentTypes") or []),
                terms_known=True,
                kind="real",
                source=LITEAPI,
                room=(first.get("name") or "").strip() or None,
                room_id=room_id,
                stay_rub=round(total),
                cancel_until=until.isoformat() if until else None,
            )
            same = (room_id or offer.room, offer.meal, until is not None)
            if same not in offers or offers[same].stay_rub > offer.stay_rub:
                offers[same] = offer
        found[hotel["hotelId"]] = sorted(offers.values(), key=lambda o: o.stay_rub)[:OFFERS_PER_HOTEL]
    return found


def occupancies(adults: int, children: tuple[int, ...]) -> list[dict]:
    """The party in rooms as the plan counts them (three to a room), every room with an adult in it."""
    rooms = max(1, min(adults, math.ceil((adults + len(children)) / ROOM_SIZE)))
    split = [{"adults": adults // rooms + (i < adults % rooms), "children": []} for i in range(rooms)]
    for age in children:
        min(split, key=lambda r: r["adults"] + len(r["children"]))["children"].append(age)
    return split


def to_price(around: tuple[Around, ...], limit: int = PRICED) -> list[Around]:
    """The hotels worth pricing: the most reviewed of every class in turn, so a budget trip has its hotels too."""
    by_class: dict[int, list[Around]] = {}
    for a in sorted(around, key=lambda a: -(a.reviews or 0)):
        by_class.setdefault(min(a.stars or 2, 5), []).append(a)
    picked: list[Around] = []
    while len(picked) < limit and any(by_class.values()):
        for stars in sorted(by_class, reverse=True):
            if by_class[stars] and len(picked) < limit:
                picked.append(by_class[stars].pop(0))
    return picked


def _encode_around(found: tuple[Around, ...]) -> dict:
    return {"hotels": [asdict(a) for a in found]}


def _decode_around(raw: dict) -> tuple[Around, ...]:
    return tuple(Around(**a) for a in raw.get("hotels") or [])


def _decode_details(raw: dict) -> Details:
    rooms = tuple(
        Room(
            **{
                **r,
                "beds": tuple(tuple(b) for b in r["beds"]),
                "views": tuple(r["views"]),
                "amenities": tuple(r["amenities"]),
                "photos": tuple(r["photos"]),
            }
        )
        for r in raw["rooms"]
    )
    return Details(
        **{
            **raw,
            "photos": tuple(raw["photos"]),
            "facilities": tuple(raw["facilities"]),
            "rooms": rooms,
            "scores": tuple(tuple(s) for s in raw["scores"]),
        }
    )


class LiteApi:
    def __init__(self, key: str, store: LookupStore | None = None, client: httpx.AsyncClient | None = None):
        self.sandbox = key.startswith("sand_")
        self._client = client or httpx.AsyncClient(
            base_url=BASE_URL, timeout=TIMEOUT_S, headers={"X-API-Key": key, "accept": "application/json"}
        )
        per_second = 4 if self.sandbox else 40  # LiteAPI allows 5 a second in the sandbox, 250 live
        self._limit = RateLimit(per_second * 60, burst=per_second)
        self._places: dict[str, Place] = {}
        self._around = Lookups(
            "lite_hotels", self._find_around, store, _encode_around, _decode_around, KEPT_FOR, MISSED_FOR
        )
        self._details = Lookups(
            "lite_hotel", self._find_details, store, asdict, _decode_details, KEPT_FOR, MISSED_FOR, per_second
        )
        self._background: set[asyncio.Task] = set()

    async def around(self, place: Place) -> tuple[Around, ...]:
        self._places[place.id] = place
        return await self._around.get(place.id) or ()

    async def details(self, ids: Iterable[str], wait_s: float | None = None) -> dict[str, Details]:
        found = await self._details.get_many(ids, wait_s)
        return {k: v for k, v in found.items() if v}

    def known(self, hotel_id: str | None) -> Details | None:
        return self._details.known(hotel_id) if hotel_id else None

    async def rates(self, ids: list[str], stay: StayQuery) -> list[dict]:
        body = {
            "hotelIds": ids,
            "occupancies": occupancies(stay.adults, stay.children),
            "currency": "RUB",
            "guestNationality": stay.nationality or "RU",
            "checkin": stay.check_in.isoformat(),
            "checkout": (stay.check_in + timedelta(days=stay.nights)).isoformat(),
            "roomMapping": True,
            "maxRatesPerHotel": OFFERS_PER_HOTEL,
            "timeout": SUPPLIER_WAIT_S,
        }
        return (await self._call("POST", "/hotels/rates", json=body)).get("data") or []

    def warm(self, places: Iterable[Place], top: int) -> None:
        """The hotels of these places and the rooms of their `top` most reviewed ones, loaded in the background:
        by the time the plan needs them, they are cached."""
        task = asyncio.create_task(self._warm(list(places), top))
        self._background.add(task)
        task.add_done_callback(self._background.discard)

    async def settle(self) -> None:
        for task in list(self._background):
            task.cancel()
        await self._around.settle()
        await self._details.settle()

    async def _warm(self, places: list[Place], top: int) -> None:
        found = await asyncio.gather(*(self.around(p) for p in places), return_exceptions=True)
        ids = [a.id for hotels in found if isinstance(hotels, tuple) for a in to_price(hotels, top)]
        await self._details.warm(ids)

    async def _find_around(self, place_id: str) -> tuple[Around, ...] | None:
        place = self._places[place_id]
        params = {"latitude": place.lat, "longitude": place.lon, "radius": RADIUS_M, "limit": LISTED}
        return around_from((await self._call("GET", "/data/hotels", params=params)).get("data") or []) or None

    async def _find_details(self, hotel_id: str) -> Details | None:
        data = (await self._call("GET", "/data/hotel", params={"hotelId": hotel_id})).get("data")
        return details_from(data) if isinstance(data, dict) and data.get("id") else None

    async def _call(self, method: str, path: str, **kwargs) -> dict:
        for (
            wait_s
        ) in BUSY_WAITS_S:  # the key's rate is shared with every process that uses it: wait, then again
            await self._limit.wait()
            response = await self._client.request(method, path, **kwargs)
            if response.status_code != 429:
                break
            await asyncio.sleep(min(float(response.headers.get("retry-after") or wait_s), MAX_BUSY_WAIT_S))
        body = response.json() if response.content else {}
        error = body.get("error") if isinstance(body, dict) else None
        if isinstance(error, dict) and error.get("code") == NO_AVAILABILITY:
            return {}
        response.raise_for_status()
        return body


class LiteOffers:
    """Offers from LiteAPI's rates. Every asked hotel gets an entry, an empty one when it has no room that night,
    so the cache knows it was asked."""

    def __init__(self, api: LiteApi, today=lambda: datetime.now(UTC).date()):
        self.api = api
        self._today = today

    async def offers(self, place: Place, hotels: list, stay: StayQuery) -> dict[str, list[Offer]]:
        found = offers_from(await self.api.rates([h.id for h in hotels], stay), stay, self._today())
        return {h.id: found.get(h.id, []) for h in hotels}
