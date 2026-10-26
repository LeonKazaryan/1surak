"""Hotels around any place from OpenStreetMap, found live through Nominatim and kept in the place_hotels table.

The seed (directory.py) covers the catalogue from Wikidata, often without stars or a website; OSM adds both,
plus the amenity tags some hotels carry (dog=yes, internet_access=wlan), and gives hotels to the places the seed
barely covers (Sochi had four) and to every city of the route map. © OpenStreetMap contributors, ODbL 1.0.
"""

import asyncio
import logging
import math
import re
import time
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.catalog.catalog import Place
from app.db import place_hotels
from app.hotels.directory import OSM_URL, Listed, hotel_id

log = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "1surak-hackathon/0.1 (https://github.com/ostrovok-hackathon-2026/beshparmak)"
LODGING = {"hotel", "guest_house", "hostel", "motel", "apartment", "chalet"}
KEPT_TAGS = (
    "internet_access",
    "internet_access:fee",
    "dog",
    "pets",
    "pets_allowed",
    "swimming_pool",
    "air_conditioning",
    "wheelchair",
    "description",
)
BOX_DEG = 0.06  # about 7 km each way from the centre: the town, not the whole region
FRESH_FOR = timedelta(days=30)
FAILED_FOR = timedelta(minutes=10)  # an outage costs one wait, not one per search
TWIN_M = 1000  # one name this close is one hotel: Wikidata and OSM place it a few hundred metres apart
NOMINATIM_GAP_S = 1.1  # its usage policy: one request a second at most


def metres(lat1: float, lon1: float, lat2: float, lon2: float) -> int:
    x = math.radians(lon2 - lon1) * math.cos(math.radians((lat1 + lat2) / 2))
    return round(6_371_000 * math.hypot(x, math.radians(lat2 - lat1)))


def _stars(value: str | None) -> int | None:
    found = re.match(r"\s*([1-5])", value or "")
    return int(found.group(1)) if found else None


def _website(tags: dict) -> str | None:
    site = (tags.get("website") or tags.get("contact:website") or "").split(";")[0].strip()
    if not site:
        return None
    return site if site.startswith(("http://", "https://")) else f"https://{site}"


def osm_listed(results: list[dict], place: Place) -> list[Listed]:
    """Nominatim's answer as directory rows: named lodgings only, with their stars, site and amenity tags."""
    found: list[Listed] = []
    for r in results:
        if (
            r.get("category") != "tourism"
            or r.get("type") not in LODGING
            or not (r.get("name") or "").strip()
        ):
            continue
        tags = r.get("extratags") or {}
        lat, lon = float(r["lat"]), float(r["lon"])
        osm = f"{r['osm_type']}/{r['osm_id']}"
        if any(
            h.name.casefold() == r["name"].strip().casefold() and metres(h.lat, h.lon, lat, lon) <= TWIN_M
            for h in found
        ):
            continue  # the same hotel mapped as a point and as its building
        found.append(
            Listed(
                id=hotel_id(place.id, {"osm": osm}),
                place_id=place.id,
                name=r["name"].strip(),
                stars=_stars(tags.get("stars")),
                lat=lat,
                lon=lon,
                centre_m=metres(place.lat, place.lon, lat, lon),
                photo=None,
                source_url=OSM_URL.format(osm),
                website=_website(tags),
                tags={k: tags[k] for k in KEPT_TAGS if tags.get(k)},
            )
        )
    return found


def _alike(a: Listed, b: Listed) -> bool:
    """«Москва» and «Москва (гостиница, Сочи)» are one hotel; two «Меркурий» a town apart are two."""
    x, y = a.name.casefold(), b.name.casefold()
    return (x in y or y in x) and metres(a.lat, a.lon, b.lat, b.lon) <= TWIN_M


def merge_listings(seed: tuple[Listed, ...], live: list[Listed]) -> tuple[Listed, ...]:
    """The seed's hotels first, each completed with what OSM knows of it; then the hotels only OSM has."""
    merged, used = [], set()
    for h in seed:
        twins = [o for o in live if o.id not in used and _alike(h, o)]
        twin = min(twins, key=lambda o: metres(h.lat, h.lon, o.lat, o.lon), default=None)
        if twin:
            used.add(twin.id)
            h = replace(
                h,
                stars=h.stars or twin.stars,
                website=h.website or twin.website,
                tags={**twin.tags, **h.tags},
            )
        merged.append(h)
    return (*merged, *(o for o in live if o.id not in used))


class OsmHotels:
    """Hotels around a place, from the table while fresh, else from Nominatim. A failure is not remembered."""

    def __init__(
        self, sessionmaker: async_sessionmaker[AsyncSession], timeout_s: float = 15.0, transport=None
    ):
        self._sessionmaker = sessionmaker
        self._timeout = timeout_s
        self._transport = transport  # tests pass an httpx.MockTransport
        self._failed: dict[str, datetime] = {}
        self._gate = asyncio.Lock()  # one OsmHotels per app: Nominatim's one request a second holds app-wide
        self._last_request = 0.0

    async def around(self, place: Place) -> list[Listed]:
        now = datetime.now(UTC)
        async with self._sessionmaker() as db:
            row = (await db.execute(select(place_hotels).where(place_hotels.c.place_id == place.id))).first()
        kept = [Listed(**h) for h in row.hotels] if row else []
        if (row and now - row.fetched_at < FRESH_FOR) or now - self._failed.get(
            place.id, now - FAILED_FOR
        ) < FAILED_FOR:
            return kept
        try:
            found = osm_listed(await self._ask(place), place)
        except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError) as error:
            log.warning("OSM hotels for %s failed: %s", place.id, error)
            self._failed[place.id] = now
            return kept
        async with self._sessionmaker() as db:
            values = {"hotels": [asdict(h) for h in found], "fetched_at": now}
            await db.execute(
                insert(place_hotels)
                .values(place_id=place.id, **values)
                .on_conflict_do_update(index_elements=["place_id"], set_=values)
            )
            await db.commit()
        return found

    async def _ask(self, place: Place) -> list[dict]:
        lon_box = BOX_DEG / max(math.cos(math.radians(place.lat)), 0.2)
        params = {
            "q": "hotel",
            "format": "jsonv2",
            "viewbox": f"{place.lon - lon_box},{place.lat + BOX_DEG},{place.lon + lon_box},{place.lat - BOX_DEG}",
            "bounded": "1",
            "extratags": "1",
            "limit": "40",
            "accept-language": "ru",
        }
        async with self._gate:  # only the spacing: requests themselves may overlap
            await asyncio.sleep(max(0.0, self._last_request + NOMINATIM_GAP_S - time.monotonic()))
            self._last_request = time.monotonic()
        async with httpx.AsyncClient(
            timeout=self._timeout, headers={"User-Agent": USER_AGENT}, transport=self._transport
        ) as client:
            response = await client.get(NOMINATIM_URL, params=params)
            response.raise_for_status()
            found = response.json()
        if not isinstance(found, list):
            raise TypeError(f"Nominatim answered {type(found).__name__}, not a list")
        return found
