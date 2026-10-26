"""A guide for any city, found live and kept: what to see, where to walk, where to eat.

The catalogue's places have a guide from Wikivoyage (seed/guide.json). Any other city, and a catalogue place
whose guide is thin, gets one from open data:
- sights and walks: one Wikidata query around the centre (a geo search, 6 km): the places with articles in many
  Wikipedias, the most written-about first (Empire State Building, the Met, Central Park…), with their Russian
  names, descriptions and Commons photos. Their types sort them: a museum, park, bridge, square or cathedral is
  a sight; a neighbourhood or an avenue is a walk; an organisation, a company, a university or an event is
  neither. A skyscraper counts only when it is iconic.
- food: restaurants from OpenStreetMap (Nominatim, bounded to the centre), the notable and the ones with a
  website first, a cuisine at most twice; the fast model turns their tags into a Russian line. With a Google
  Places key, the best rated places (rating and number of reviews) come first; Google's terms allow no
  storing, so those stay in memory for a day.
Kept 60 days in the lookups table. Wikidata is CC0, OSM ODbL; each photo keeps its own licence.
"""

import asyncio
import html
import json
import logging
import math
import re
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import unquote

import httpx

from app.catalog.catalog import Place
from app.lookups import Lookups, LookupStore
from app.plan.guide import Guide, Spot, guide_for, parse_guide

log = logging.getLogger(__name__)

USER_AGENT = "1surak-hackathon/0.1 (https://github.com/ostrovok-hackathon-2026/beshparmak)"
SPARQL = "https://query.wikidata.org/sparql"
NOMINATIM = "https://nominatim.openstreetmap.org/search"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
GOOGLE_SEARCH = "https://places.googleapis.com/v1/places:searchText"
RADIUS_KM = 6
FOOD_BOX_DEG = 0.03  # about 3 km each way: restaurants near the centre, not the suburbs
MIN_LINKS = 12  # Wikipedias writing about a place: fewer is a local building, not a sight
ICONIC_LINKS = 70  # a skyscraper is a sight only this famous (the Empire State Building, not an office tower)
STAR_LINKS = 60
MAX_SIGHTS, MAX_WALKS, MAX_FOOD = 16, 6, 14
SAME_CUISINE = 2
PHOTOS = 12
PHOTO_WIDTH = 640
THIN_SIGHTS, THIN_FOOD = 6, 4  # a seed guide with fewer gets the live one added
TWIN_M = 150  # one name this close is one place
FOUND_TTL, MISSED_TTL = timedelta(days=60), timedelta(days=3)
GOOGLE_TTL_S = 24 * 3600
NOMINATIM_GAP_S = 1.1  # its usage policy: one request a second

SIGHT = re.compile(
    r"museum|park|garden|square|plaza|bridge|monument|memorial|statue|sculpture|cathedral|church|basilica|"
    r"mosque|temple|synagogue|shrine|monastery|abbey|castle|palace|fort|citadel|kremlin|tower|observation|"
    r"landmark|attraction|zoo|aquarium|gallery|theat|opera|concert hall|performing arts|market|bazaar|beach|"
    r"viewpoint|archaeolog|ruins|historic site|gate|fountain|botanical|amusement|promenade|waterfront|lighthouse",
    re.IGNORECASE,
)
# a type that says the item is not a place to visit, unless a plain place type is there too (the Met is also a
# «production company»; the Broadway theatre is a «theatrical genre», New Amsterdam a «former settlement»)
NOT_A_PLACE = re.compile(r"genre|former|settlement|colony|school|university|college|diocese", re.IGNORECASE)
PLAIN_PLACE = re.compile(
    r"museum|park|garden|cathedral|church|mosque|temple|bridge|monument|memorial|statue|castle|palace|square|zoo",
    re.IGNORECASE,
)
# a food spot without a cuisine says what it is, not a cuisine someone guessed
FOOD_KIND = {"restaurant": "Ресторан", "cafe": "Кафе", "fast_food": "Фастфуд", "bar": "Бар", "pub": "Паб"}
WALK = re.compile(
    r"neighbou?rhood|district|quarter|old town|historic cent|avenue|boulevard|street|embankment",
    re.IGNORECASE,
)
QUERY = """SELECT ?item ?links (SAMPLE(?ru) AS ?name) (SAMPLE(?en) AS ?name_en) (SAMPLE(?d) AS ?about)
  (SAMPLE(?loc) AS ?at) (SAMPLE(?img) AS ?image) (GROUP_CONCAT(DISTINCT ?typeLabel; separator="|") AS ?types)
WHERE {
  SERVICE wikibase:around { ?item wdt:P625 ?loc .
    bd:serviceParam wikibase:center "Point(%(lon)s %(lat)s)"^^geo:wktLiteral ; wikibase:radius "%(km)s" . }
  ?item wikibase:sitelinks ?links . FILTER(?links >= %(links)s)
  OPTIONAL { ?item wdt:P31 ?type . ?type rdfs:label ?typeLabel FILTER(lang(?typeLabel) = "en") }
  OPTIONAL { ?item rdfs:label ?ru FILTER(lang(?ru) = "ru") }
  OPTIONAL { ?item rdfs:label ?en FILTER(lang(?en) = "en") }
  OPTIONAL { ?item schema:description ?d FILTER(lang(?d) = "ru") }
  OPTIONAL { ?item wdt:P18 ?img }
} GROUP BY ?item ?links ORDER BY DESC(?links) LIMIT 150"""
NOTES_PROMPT = (
    "Ты переводишь на русский теги кухни из OpenStreetMap для подписей в путеводителе. Для каждой строки дан "
    "тег вроде «italian;pizza» или «coffee_shop». Напиши по каждой одну подпись в 2-5 слов, только перевод "
    "тега: «итальянская кухня и пицца», «кофейня». Ничего не добавляй: ни оценок, ни цен, ни догадок. Порядок "
    "и число подписей — как у строк."
)
NOTES_SCHEMA = {
    "type": "object",
    "properties": {"notes": {"type": "array", "items": {"type": "string"}}},
    "required": ["notes"],
    "additionalProperties": False,
}


def km_between(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance (here, not from app.trip, which imports this module for its cards)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    h = (
        math.sin((p2 - p1) / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    )
    return 6371 * 2 * math.asin(math.sqrt(h))


def kind_of(types: str, links: int) -> str | None:
    """see, walk or None, from the Wikidata types of a place (their English labels)."""
    labels = [t for t in types.split("|") if t]
    if any(NOT_A_PLACE.search(t) for t in labels) and not any(PLAIN_PLACE.search(t) for t in labels):
        return None
    if any(SIGHT.search(t) for t in labels):
        return "see"
    if any("skyscraper" in t for t in labels):
        return "see" if links >= ICONIC_LINKS else None
    if any(WALK.search(t) for t in labels):
        return "walk"
    return None


def _point(wkt: str | None) -> tuple[float | None, float | None]:
    found = re.match(r"Point\(([-\d.]+) ([-\d.]+)\)", wkt or "")
    return (float(found.group(2)), float(found.group(1))) if found else (None, None)


def _plain(text: str | None) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", text or "")).strip()


def _sentence(text: str | None) -> str:
    text = (text or "").strip()
    return text[:1].upper() + text[1:] if text else ""


def _value(row: dict, key: str) -> str | None:
    return row.get(key, {}).get("value")


def sights_from(rows: list[dict], place_id: str) -> tuple[list[dict], list[dict], dict[str, str]]:
    """Sights and walks, the most written-about first, and the Commons file of each sight that has one."""
    sights, walks, files = [], [], {}
    for row in rows:
        links = int(_value(row, "links") or 0)
        kind = kind_of(_value(row, "types") or "", links)
        name = _value(row, "name") or _value(row, "name_en")
        if kind is None or not name or re.fullmatch(r"Q\d+", name):
            continue
        qid = (_value(row, "item") or "").rsplit("/", 1)[-1]
        lat, lon = _point(_value(row, "at"))
        listing = {
            "id": f"{place_id}-wd-{qid.lower()}",
            "type": kind,
            "name": name,
            "summary": _sentence(_value(row, "about")),
            "lat": lat,
            "lon": lon,
            "star": links >= STAR_LINKS,
            "source_url": f"https://www.wikidata.org/wiki/{qid}",
            "links": links,
        }
        (sights if kind == "see" else walks).append(listing)
        if kind == "see" and _value(row, "image"):
            files[listing["id"]] = unquote(_value(row, "image").rsplit("/", 1)[-1])  # «Empire%20State…»
    return sights[:MAX_SIGHTS], walks[:MAX_WALKS], files


def food_from(results: list[dict], centre: tuple[float, float]) -> list[dict]:
    """Restaurants and cafés from Nominatim: the notable and the ones with a website first, then the nearest;
    a cuisine at most twice, so the meals differ."""
    seen: dict[str, int] = {}
    ranked = sorted(
        (r for r in results if r.get("name")),
        key=lambda r: (
            not (r.get("extratags") or {}).get("wikidata"),
            not (r.get("extratags") or {}).get("website"),
            km_between(*centre, float(r["lat"]), float(r["lon"])),
        ),
    )
    food = []
    for r in ranked:
        tags = r.get("extratags") or {}
        cuisine = (tags.get("cuisine") or "").split(";")[0].strip().lower()
        if cuisine and seen.get(cuisine, 0) >= SAME_CUISINE:
            continue
        if cuisine:
            seen[cuisine] = seen.get(cuisine, 0) + 1
        food.append(
            {
                "id": f"osm-{r.get('osm_type', 'n')[:1]}{r.get('osm_id')}",
                "type": "drink" if r.get("type") in ("cafe", "bar", "pub") else "eat",
                "name": r["name"],
                "summary": FOOD_KIND.get(r.get("type"), "Ресторан"),
                "lat": float(r["lat"]),
                "lon": float(r["lon"]),
                "hours": tags.get("opening_hours"),
                "source_url": f"https://www.openstreetmap.org/{r.get('osm_type', 'node')}/{r.get('osm_id')}",
                "cuisine": tags.get("cuisine"),
            }
        )
        if len(food) == MAX_FOOD:
            break
    return food


def google_food(places: list[dict]) -> list[dict]:
    """Google Places' best rated, by a rating weighed by its number of reviews."""

    def score(p: dict) -> float:
        count, rating = p.get("userRatingCount") or 0, p.get("rating") or 0
        return (count * rating + 200 * 4.0) / (count + 200)

    food = []
    for p in sorted((p for p in places if p.get("rating")), key=score, reverse=True)[:MAX_FOOD]:
        kind = (p.get("primaryTypeDisplayName") or {}).get("text") or "ресторан"
        reviews = f"{p.get('userRatingCount', 0):,}".replace(",", " ")
        food.append(
            {
                "id": f"gp-{p.get('id')}",
                "type": "eat",
                "name": (p.get("displayName") or {}).get("text") or kind,
                "summary": f"★ {p['rating']:.1f} · {reviews} отзывов в Google · {kind.lower()}",
                "lat": (p.get("location") or {}).get("latitude"),
                "lon": (p.get("location") or {}).get("longitude"),
                "source_url": p.get("googleMapsUri"),
            }
        )
    return food


def _alike(a: Spot, b: Spot) -> bool:
    near = a.lat is not None and b.lat is not None and km_between(a.lat, a.lon, b.lat, b.lon) * 1000 <= TWIN_M
    return a.name.casefold() == b.name.casefold() or (near and a.name[:5].casefold() == b.name[:5].casefold())


def merged(seed: Guide, live: Guide | None, food: Iterable[Spot] = ()) -> Guide:
    """The seed's own spots first (checked by people), then the live ones it does not have."""
    if live is None and not food:
        return seed

    def add(base: tuple[Spot, ...], more: Iterable[Spot]) -> tuple[Spot, ...]:
        kept = list(base)
        for spot in more:
            if not any(_alike(spot, k) for k in kept):
                kept.append(spot)
        return tuple(kept)

    return Guide(
        place_id=seed.place_id,
        sights=add(seed.sights, live.sights if live else ()),
        food=add(tuple(food), add(seed.food, live.food if live else ())),
        dishes=seed.dishes,
        food_intro=seed.food_intro,
        photo=seed.photo,
        source_url=seed.source_url,
    )


class LiveGuides:
    def __init__(
        self,
        store: LookupStore | None,
        places: Callable[[str], Place | None],
        client: Any = None,  # the model that writes the food lines; None: the cuisine tag as it is
        model: str = "",
        google_key: str = "",
        transport: httpx.AsyncBaseTransport | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self._places = places
        self._client, self._model = client, model
        self._google_key = google_key
        self._transport = transport
        self._google: dict[str, tuple[float, list[Spot]]] = {}
        self._gate = asyncio.Lock()
        self._last = 0.0
        self.cache = Lookups(
            "city_guide",
            self._find,
            store,
            lambda raw: raw,
            lambda raw: raw,
            FOUND_TTL,
            MISSED_TTL,
            at_once=2,
            now=now,
        )

    def _thin(self, place_id: str) -> bool:
        seed = guide_for(place_id)
        return len(seed.sights) < THIN_SIGHTS or len(seed.food) < THIN_FOOD

    async def warm(self, place_ids: Iterable[str]) -> None:
        await self.cache.warm(p for p in place_ids if self._thin(p))

    async def guide(self, place: Place, wait_s: float) -> Guide:
        """The place's guide: the seed's, with the live sights, walks and food added where it is thin."""
        seed = guide_for(place.id)
        if not self._thin(place.id):
            return seed
        raw, google = await asyncio.gather(self.cache.get(place.id, wait_s), self._google_food(place))
        live = parse_guide(place.id, raw) if raw else None
        return merged(seed, live, google)

    async def _find(self, place_id: str) -> dict | None:
        place = self._places(place_id)
        if place is None:
            return None
        async with httpx.AsyncClient(
            timeout=20, headers={"User-Agent": USER_AGENT}, transport=self._transport
        ) as client:
            rows, food = await asyncio.gather(self._wikidata(client, place), self._nominatim(client, place))
            sights, walks, files = sights_from(rows, place.id)
            photos = await self._photos(client, list(files.values())[:PHOTOS])
        for listing in sights:
            if (file := files.get(listing["id"])) and (photo := photos.get(file)):
                listing["photo"] = photo
        await self._notes(food)
        if not sights and not walks and not food:
            return None
        return {"listings": [*sights, *walks, *food], "source_url": "https://www.wikidata.org"}

    async def _wikidata(self, client: httpx.AsyncClient, place: Place) -> list[dict]:
        query = QUERY % {"lat": place.lat, "lon": place.lon, "km": RADIUS_KM, "links": MIN_LINKS}
        response = await client.get(
            SPARQL, params={"query": query}, headers={"Accept": "application/sparql-results+json"}
        )
        response.raise_for_status()
        return response.json()["results"]["bindings"]

    async def _nominatim(self, client: httpx.AsyncClient, place: Place) -> list[dict]:
        lon_box = FOOD_BOX_DEG / max(math.cos(math.radians(place.lat)), 0.2)
        params = {
            "q": "restaurant",
            "format": "jsonv2",
            "viewbox": f"{place.lon - lon_box},{place.lat + FOOD_BOX_DEG},{place.lon + lon_box},{place.lat - FOOD_BOX_DEG}",
            "bounded": "1",
            "extratags": "1",
            "limit": "40",
            "accept-language": "ru",
        }
        async with self._gate:  # only the spacing: Nominatim asks for one request a second
            await asyncio.sleep(max(0.0, self._last + NOMINATIM_GAP_S - time.monotonic()))
            self._last = time.monotonic()
        try:
            response = await client.get(NOMINATIM, params=params)
            response.raise_for_status()
            found = response.json()
        except (httpx.HTTPError, ValueError) as problem:
            log.warning("Restaurants for %s unavailable: %s", place.id, type(problem).__name__)
            return []
        return food_from(found if isinstance(found, list) else [], (place.lat, place.lon))

    async def _photos(self, client: httpx.AsyncClient, files: list[str]) -> dict[str, dict]:
        """Commons thumbnails with their author and licence, for many files in one request."""
        if not files:
            return {}
        try:
            response = await client.get(
                COMMONS_API,
                params={
                    "action": "query",
                    "format": "json",
                    "titles": "|".join(f"File:{f}" for f in files),
                    "prop": "imageinfo",
                    "iiprop": "url|size|extmetadata",
                    "iiurlwidth": PHOTO_WIDTH,
                    "iiextmetadatafilter": "Artist|LicenseShortName",
                },
            )
            response.raise_for_status()
            pages = response.json().get("query", {}).get("pages", {}).values()
        except (httpx.HTTPError, ValueError) as problem:
            log.warning("Commons photos unavailable: %s", type(problem).__name__)
            return {}
        photos = {}
        for page in pages:
            info = (page.get("imageinfo") or [None])[0]
            if not info or not info.get("thumburl"):
                continue
            meta = info.get("extmetadata", {})
            file = page.get("title", "").removeprefix("File:")
            photos[file.replace(" ", "_")] = photos[file] = {
                "url": info["thumburl"].split("?")[0],
                "width": info.get("thumbwidth") or PHOTO_WIDTH,
                "height": info.get("thumbheight") or PHOTO_WIDTH,
                "author": _plain(meta.get("Artist", {}).get("value")) or "Wikimedia Commons",
                "license": _plain(meta.get("LicenseShortName", {}).get("value")),
                "file_url": info.get("descriptionurl"),
            }
        return photos

    async def _notes(self, food: list[dict]) -> None:
        """The cuisine tags of the food spots in Russian, in one call to the fast model; a spot without a
        cuisine keeps saying what it is («Ресторан», «Кафе»)."""
        tagged = [(spot, cuisine) for spot in food if (cuisine := spot.pop("cuisine", None))]
        for spot, cuisine in tagged:
            spot["summary"] = cuisine.replace("_", " ").replace(";", ", ")
        if not tagged or self._client is None:
            return
        listing = "\n".join(f"{i}. {cuisine}" for i, (_, cuisine) in enumerate(tagged, 1))
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "system", "content": NOTES_PROMPT}, {"role": "user", "content": listing}],
                response_format={
                    "type": "json_schema",
                    "json_schema": {"name": "notes", "strict": True, "schema": NOTES_SCHEMA},
                },
                max_completion_tokens=800,
            )
            notes = json.loads(response.choices[0].message.content or "{}").get("notes") or []
        except Exception:
            log.warning("Food notes failed", exc_info=True)
            return
        if len(notes) == len(tagged):
            for (spot, _), note in zip(tagged, notes, strict=True):
                spot["summary"] = _sentence(str(note)[:80])

    async def _google_food(self, place: Place) -> list[Spot]:
        """The best rated places from Google Places, when there is a key; kept in memory only, for a day."""
        if not self._google_key:
            return []
        cached = self._google.get(place.id)
        if cached and time.monotonic() - cached[0] < GOOGLE_TTL_S:
            return cached[1]
        body = {
            "textQuery": f"лучшие рестораны {place.name}",
            "languageCode": "ru",
            "maxResultCount": 20,
            "locationBias": {
                "circle": {"center": {"latitude": place.lat, "longitude": place.lon}, "radius": 5000.0}
            },
        }
        fields = (
            "places.id,places.displayName,places.rating,places.userRatingCount,places.location,"
            "places.primaryTypeDisplayName,places.googleMapsUri"
        )
        try:
            async with httpx.AsyncClient(timeout=10, transport=self._transport) as client:
                response = await client.post(
                    GOOGLE_SEARCH,
                    json=body,
                    headers={"X-Goog-Api-Key": self._google_key, "X-Goog-FieldMask": fields},
                )
                response.raise_for_status()
                spots = parse_guide(
                    place.id, {"listings": google_food(response.json().get("places", []))}
                ).food
        except (httpx.HTTPError, ValueError) as problem:
            log.warning("Google Places for %s unavailable: %s", place.id, type(problem).__name__)
            return []
        self._google[place.id] = (time.monotonic(), list(spots))
        return list(spots)

    async def settle(self) -> None:
        await self.cache.settle()


@dataclass
class SeedGuides:
    """No live data (tests, or switched off): the seed's guide as it is."""

    async def warm(self, place_ids: Iterable[str]) -> None:
        return None

    async def guide(self, place: Place, wait_s: float) -> Guide:
        return guide_for(place.id)

    async def settle(self) -> None:
        return None


_guides: LiveGuides | SeedGuides = SeedGuides()


def configure(guides: LiveGuides | SeedGuides) -> None:
    global _guides
    _guides = guides


def guides() -> LiveGuides | SeedGuides:
    return _guides
