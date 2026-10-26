"""A photo for any place, found live: the guide's checked photo first, else Wikidata's image of the place.

A place from the catalogue carries its Wikidata id; a city from the route map is found on Russian Wikipedia by
its name and kept only if the article sits near the city's coordinates. The image is Wikidata's main image
(P18), or the article's lead image when it has none, never a map, flag or coat of arms. Its author and licence
come from Commons. Found photos and misses are kept in the place_photos table; a miss is retried after a week.
"""

import asyncio
import logging
import math
import re
from datetime import UTC, datetime, timedelta
from difflib import SequenceMatcher
from html import unescape

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.catalog import Place
from app.db import place_photos
from app.plan.guide import guide_for

log = logging.getLogger(__name__)

HEADERS = {"User-Agent": "1surak/1.0 (https://github.com/ostrovok-hackathon-2026/beshparmak)"}
WIKI_API = "https://ru.wikipedia.org/w/api.php"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
WIDTH = 1280
NEARBY_M = 10_000  # the radius Wikipedia's geosearch allows at most
ALIKE = 0.7  # how close an article title must read to the name: «Мекеле» and «Мэкэле» pass
NEAR_KM = 150  # an article farther than this from the place is about something else with the same name
FOUND_FOR = timedelta(days=90)
MISSED_FOR = timedelta(days=7)
BUDGET_S = 6.0  # cards wait at most this long for photos; the rest come with the next search
NOT_A_PHOTO = re.compile(
    r"\.svg$|flag|coat|seal|emblem|logo|locator|location|map|герб|флаг|карта", re.IGNORECASE
)

_found: dict[str, dict | None] = {}  # place id → photo or a miss, for this process


def place_photo(place_id: str) -> dict | None:
    """The photo a card shows: the guide's, else one found live (call ensure_photos first)."""
    photo = guide_for(place_id).photo
    return photo.view() if photo else _found.get(place_id)


def _km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (
        math.sin((p2 - p1) / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    )
    return 6371 * 2 * math.asin(math.sqrt(a))


def _plain(text: str) -> str:
    return text.casefold().replace("э", "е").replace("ё", "е").split(" (")[0].split(",")[0]


def _alike(name: str, title: str) -> float:
    return SequenceMatcher(None, _plain(name), _plain(title)).ratio()


def _text(html: str | None) -> str:
    return unescape(re.sub(r"<[^>]+>", "", html or "")).strip()


class PhotoFinder:
    def __init__(self, client: httpx.AsyncClient | None = None, timeout_s: float = 5.0):
        self._client = client or httpx.AsyncClient(timeout=timeout_s, headers=HEADERS)

    async def _get(self, url: str, **params) -> dict:
        r = await self._client.get(url, params={"format": "json", "formatversion": 2, **params})
        r.raise_for_status()
        return r.json()

    async def _article(self, place: Place) -> tuple[str | None, str | None]:
        """The Wikidata id and lead image of the Russian article about the place, by name and position."""
        data = await self._get(
            WIKI_API,
            action="query",
            generator="search",
            gsrsearch=place.name,
            gsrlimit=4,
            gsrnamespace=0,
            prop="coordinates|pageimages|pageprops",
            piprop="name",
            ppprop="wikibase_item",
        )
        pages = sorted(data.get("query", {}).get("pages", []), key=lambda p: p.get("index", 99))
        for page in pages:
            spot = (page.get("coordinates") or [None])[0]
            near = spot and _km(place.lat, place.lon, spot["lat"], spot["lon"]) <= NEAR_KM
            if near and _alike(place.name, page.get("title", "")) >= ALIKE:
                return page.get("pageprops", {}).get("wikibase_item"), page.get("pageimage")
        return await self._nearby(place)

    async def _nearby(self, place: Place) -> tuple[str | None, str | None]:
        """The article next to the city's coordinates whose title reads like its name: Wikipedia spells
        «Мекеле» as «Мэкэле», so the name search alone misses it."""
        data = await self._get(
            WIKI_API,
            action="query",
            generator="geosearch",
            ggscoord=f"{place.lat}|{place.lon}",
            ggsradius=NEARBY_M,
            ggslimit=30,
            prop="pageimages|pageprops",
            piprop="name",
            ppprop="wikibase_item",
        )
        scored = [(_alike(place.name, p.get("title", "")), p) for p in data.get("query", {}).get("pages", [])]
        score, page = max(scored, key=lambda pair: pair[0], default=(0.0, None))
        if page is None or score < ALIKE:
            return None, None
        return page.get("pageprops", {}).get("wikibase_item"), page.get("pageimage")

    async def _wikidata_image(self, qid: str) -> str | None:
        data = await self._get(WIKIDATA_API, action="wbgetclaims", entity=qid, property="P18")
        for claim in data.get("claims", {}).get("P18", []):
            value = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
            if value and not NOT_A_PHOTO.search(value):
                return value
        return None

    async def _commons(self, file: str) -> dict | None:
        data = await self._get(
            COMMONS_API,
            action="query",
            titles=f"File:{file}",
            prop="imageinfo",
            iiprop="url|size|extmetadata",
            iiurlwidth=WIDTH,
            iiextmetadatafilter="Artist|LicenseShortName",
        )
        pages = data.get("query", {}).get("pages", [])
        info = (pages[0].get("imageinfo") or [None])[0] if pages else None
        if not info or not info.get("thumburl"):
            return None
        meta = info.get("extmetadata", {})
        return {
            "url": info["thumburl"].split("?")[0],
            "width": info.get("thumbwidth") or info.get("width"),
            "height": info.get("thumbheight") or info.get("height"),
            "author": _text(meta.get("Artist", {}).get("value")) or "Wikimedia Commons",
            "license": _text(meta.get("LicenseShortName", {}).get("value")),
            "file_url": info.get("descriptionurl"),
        }

    async def find(self, place: Place) -> dict | None:
        qid = place.qid if place.qid.startswith("Q") else None
        lead = None
        if qid is None:
            qid, lead = await self._article(place)
        file = (await self._wikidata_image(qid) if qid else None) or (
            lead if lead and not NOT_A_PHOTO.search(lead) else None
        )
        return await self._commons(file) if file else None


_finder: PhotoFinder | None = None


def finder() -> PhotoFinder:
    global _finder
    if _finder is None:
        _finder = PhotoFinder()
    return _finder


async def _load(db: AsyncSession, ids: list[str], now: datetime) -> None:
    try:
        rows = (await db.execute(select(place_photos).where(place_photos.c.place_id.in_(ids)))).all()
    except Exception:
        log.warning("Could not read cached photos", exc_info=True)
        return
    for row in rows:
        age = now - (row.fetched_at if row.fetched_at.tzinfo else row.fetched_at.replace(tzinfo=UTC))
        if age < (FOUND_FOR if row.photo else MISSED_FOR):
            _found[row.place_id] = row.photo


async def _save(db: AsyncSession, found: dict[str, dict | None], now: datetime) -> None:
    try:
        for place_id, photo in found.items():
            stmt = insert(place_photos).values(place_id=place_id, photo=photo, fetched_at=now)
            await db.execute(
                stmt.on_conflict_do_update(
                    index_elements=["place_id"], set_={"photo": photo, "fetched_at": now}
                )
            )
        await db.commit()
    except Exception:
        log.warning("Could not cache photos", exc_info=True)
        await db.rollback()


async def ensure_photos(db: AsyncSession, places: list[Place], now: datetime | None = None) -> None:
    """Find the photos these places lack, all at once and within BUDGET_S, so place_photo() has them."""
    now = now or datetime.now(UTC)
    wanted = {p.id: p for p in places if guide_for(p.id).photo is None and p.id not in _found}
    if not wanted:
        return
    await _load(db, list(wanted), now)
    todo = [p for pid, p in wanted.items() if pid not in _found]
    if not todo:
        return

    async def one(place: Place) -> tuple[str, dict | None] | None:
        try:
            return place.id, await finder().find(place)
        except (httpx.HTTPError, ValueError, KeyError) as e:  # a hiccup is not a miss: try again next time
            log.info("No photo for %s: %s", place.id, e)
            return None

    tasks = [asyncio.create_task(one(p)) for p in todo]
    done, pending = await asyncio.wait(tasks, timeout=BUDGET_S)
    for task in pending:
        task.cancel()
    found = dict(r for t in done if (r := t.result()))
    _found.update(found)
    await _save(db, found, now)
