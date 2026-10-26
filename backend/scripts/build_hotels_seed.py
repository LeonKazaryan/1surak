"""Builds the hotel directory: real hotels around every catalogue place, with stars and photos where known.

Run: cd backend && python -m scripts.build_hotels_seed                (Wikidata for all places, a few minutes)
     python -m scripts.build_hotels_seed --osm          (adds OpenStreetMap: stars, more hotels; slow, resumable)
     python -m scripts.build_hotels_seed --osm --place kazan

Two sources, merged by name and distance:
- Wikidata (CC0): hotels with coordinates, and a photo (P18) for the notable ones. Stable endpoint.
- OpenStreetMap (ODbL): more hotels, and stars. The public Overpass servers are often overloaded, so every
  answer is cached per place and failures are retried with backoff; a rerun only asks for what is missing.
Photos come only from Wikimedia Commons under a free licence, with the author (rule 6.5: no hotel photos
from booking sites). Prices are not here: they are offers (app/hotels/offers.py), cached apart.
"""

import argparse
import json
import math
import re
import time
from pathlib import Path
from urllib.parse import unquote

import httpx

from app.catalog.catalog import load_catalog
from scripts.build_guide_seed import USER_AGENT, fetch_commons, file_title

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "app" / "hotels" / "seed" / "hotels.json"
CACHE = ROOT / ".cache" / "hotels"
WIKIDATA = "https://query.wikidata.org/sparql"
OVERPASS = (
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass-api.de/api/interpreter",
)
RADIUS_KM = {"city": 5, "sea": 9, "ski": 8, "mountains": 12, "nature": 15}
MAX_PER_PLACE = 30
SAME_HOTEL_M = 250  # the same name this close is one hotel mapped twice
PHOTO_WIDTH = 640
TRIES = 4
OSM_TIMEOUT_S = 50
NOISE = re.compile(r"\b(hotel|отель|гостиница|гостевой дом|resort|spa|&)\b", re.IGNORECASE)


def radius(kinds: tuple[str, ...]) -> float:
    return max(RADIUS_KM.get(k, 6) for k in kinds) if kinds else 6


def metres(a: tuple[float, float], b: tuple[float, float]) -> float:
    x = math.radians(b[1] - a[1]) * math.cos(math.radians((a[0] + b[0]) / 2))
    return 6_371_000 * math.hypot(x, math.radians(b[0] - a[0]))


def key(name: str) -> str:
    return re.sub(r"\W+", " ", NOISE.sub(" ", name.casefold())).strip()


def cached(name: str, fetch):
    path = CACHE / f"{name}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    data = fetch()
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


def retrying(call):
    for attempt in range(TRIES):
        try:
            return call()
        except (httpx.HTTPError, ValueError) as error:
            wait = min(60, 4 * 2**attempt)
            print(f"    retry in {wait}s: {error.__class__.__name__} {str(error)[:80]}")
            time.sleep(wait)
    raise RuntimeError("gave up")


def commons_title(image: str | None) -> str | None:
    """Wikidata gives «…/Special:FilePath/Kazan%20hotel.jpg», OSM «File:Kazan hotel.jpg»: both to a File: title."""
    if not image:
        return None
    if "Special:FilePath/" in image:
        image = unquote(image.rsplit("Special:FilePath/", 1)[1])
    return file_title(image)


def wikidata_hotels(lat: float, lon: float, km: float) -> list[dict]:
    query = f"""SELECT ?h ?hLabel ?image ?coord WHERE {{
  SERVICE wikibase:around {{ ?h wdt:P625 ?coord . bd:serviceParam wikibase:center "Point({lon} {lat})"^^geo:wktLiteral .
    bd:serviceParam wikibase:radius "{km}" . }}
  ?h wdt:P31/wdt:P279* wd:Q27686 .
  FILTER NOT EXISTS {{ ?h wdt:P576 ?closed }}
  OPTIONAL {{ ?h wdt:P18 ?image }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "ru,en" . }}
}} LIMIT 300"""

    def call():
        response = httpx.get(
            WIKIDATA,
            params={"query": query, "format": "json"},
            headers={"User-Agent": USER_AGENT},
            timeout=90,
        )
        response.raise_for_status()
        return response.json()["results"]["bindings"]

    rows = retrying(call)
    found = {}
    for r in rows:
        qid = r["h"]["value"].rsplit("/", 1)[-1]
        label = r["hLabel"]["value"]
        point = re.findall(r"[-\d.]+", r["coord"]["value"])
        if label == qid or len(point) != 2:
            continue  # no name in Russian or English
        found.setdefault(
            qid,
            {
                "name": label,
                "lat": float(point[1]),
                "lon": float(point[0]),
                "qid": qid,
                "image": r.get("image", {}).get("value"),
            },
        )
    return list(found.values())


def bbox(lat: float, lon: float, km: float) -> str:
    d = km / 111.0
    e = d / max(0.2, math.cos(math.radians(lat)))
    return f"{lat - d:.4f},{lon - e:.4f},{lat + d:.4f},{lon + e:.4f}"


def overpass(query: str) -> list[dict]:
    last = None
    for url in OVERPASS:
        try:
            # a hard limit: an overloaded server may keep the connection open without answering
            limit = httpx.Timeout(OSM_TIMEOUT_S, connect=10)
            response = httpx.post(
                url, data={"data": query}, headers={"User-Agent": USER_AGENT}, timeout=limit
            )
            response.raise_for_status()
            return response.json()["elements"]
        except (httpx.HTTPError, ValueError) as error:
            last = error
    raise last


def osm_hotels(lat: float, lon: float, km: float) -> list[dict]:
    box = bbox(lat, lon, km)
    rows = []
    # points and areas apart: one query for both times out on the public servers
    for kind, out in (("node", "out;"), ("way", "out center tags;")):
        query = f"[out:json][timeout:45];{kind}[tourism=hotel][name]({box});{out}"
        rows += overpass(query)  # one try per server: a failed place is skipped and asked again on a rerun
    found = []
    for e in rows:
        tags = e.get("tags", {})
        point = (
            (e.get("lat"), e.get("lon")) if e["type"] == "node" else (e["center"]["lat"], e["center"]["lon"])
        )
        stars = re.match(r"^([1-5])", tags.get("stars", ""))
        found.append(
            {
                "name": tags.get("name:ru") or tags["name"],
                "lat": point[0],
                "lon": point[1],
                "osm": f"{e['type']}/{e['id']}",
                "stars": int(stars.group(1)) if stars else None,
                "qid": tags.get("wikidata"),
                "image": tags.get("wikimedia_commons")
                if tags.get("wikimedia_commons", "").startswith("File:")
                else None,
                "website": tags.get("website") or tags.get("contact:website"),
            }
        )
    return found


def merge(wd: list[dict], osm: list[dict]) -> list[dict]:
    """One row per hotel: OSM gives stars and the website, Wikidata the photo; matched by QID, else name and place."""
    merged = [dict(h) for h in osm]
    by_qid = {h["qid"]: h for h in merged if h.get("qid")}
    for w in wd:
        twin = by_qid.get(w["qid"]) or next(
            (
                h
                for h in merged
                if key(h["name"]) == key(w["name"])
                and metres((h["lat"], h["lon"]), (w["lat"], w["lon"])) < SAME_HOTEL_M
            ),
            None,
        )
        if twin:
            twin["qid"] = twin.get("qid") or w["qid"]
            twin["image"] = twin.get("image") or w["image"]
        else:
            merged.append({**w, "stars": None, "osm": None, "website": None})
    # the same hotel mapped as a point and an area
    unique: list[dict] = []
    for h in merged:
        if not any(
            key(u["name"]) == key(h["name"])
            and metres((u["lat"], u["lon"]), (h["lat"], h["lon"])) < SAME_HOTEL_M
            for u in unique
        ):
            unique.append(h)
    return unique


def pick(hotels: list[dict], centre: tuple[float, float]) -> list[dict]:
    """The hotels worth offering: known stars and photos first, then the closest to the centre."""
    for h in hotels:
        h["centre_m"] = round(metres(centre, (h["lat"], h["lon"])))
    ranked = sorted(hotels, key=lambda h: (h["stars"] is None, h["image"] is None, h["centre_m"]))
    return ranked[:MAX_PER_PLACE]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--place", action="append", help="only these place ids")
    parser.add_argument("--osm", action="store_true", help="also ask OpenStreetMap (slow, often overloaded)")
    args = parser.parse_args()
    places = [p for p in load_catalog().places if not args.place or p.id in args.place]
    result = json.loads(OUT.read_text(encoding="utf-8"))["places"] if OUT.exists() else {}
    for i, place in enumerate(places, 1):
        km = radius(place.kinds)
        print(f"[{i}/{len(places)}] {place.id} ({km} km)")
        try:
            wd = cached(f"{place.id}.wikidata", lambda p=place, r=km: wikidata_hotels(p.lat, p.lon, r))
        except RuntimeError:
            wd = []
            print("    Wikidata did not answer; rerun later")
        osm_path = CACHE / f"{place.id}.osm.json"
        osm = json.loads(osm_path.read_text(encoding="utf-8")) if osm_path.exists() else []
        if args.osm and not osm_path.exists():
            try:
                osm = cached(f"{place.id}.osm", lambda p=place, r=km: osm_hotels(p.lat, p.lon, r))
            except (httpx.HTTPError, ValueError) as error:
                print(f"    OpenStreetMap did not answer ({error.__class__.__name__}); rerun --osm later")
        if not wd and not osm:
            continue
        chosen = pick(merge(wd, osm), (place.lat, place.lon))
        print(f"    wikidata {len(wd)}, osm {len(osm)} -> {len(chosen)} hotels")
        result[place.id] = chosen

    titles = {commons_title(h["image"]) for hs in result.values() for h in hs if h.get("image")}
    photos = fetch_commons([t for t in titles if t], PHOTO_WIDTH) if titles else {}
    for hotels in result.values():
        for h in hotels:
            h["photo"] = photos.get(commons_title(h["image"])) if h.get("image") else None
    OUT.parent.mkdir(parents=True, exist_ok=True)
    about = (
        "Hotels around catalogue places from Wikidata (CC0) and OpenStreetMap (© OpenStreetMap contributors, "
        "ODbL 1.0); photos from Wikimedia Commons with their authors and licences. See NOTICE.md. "
        "No prices: those are offers, cached apart."
    )
    OUT.write_text(
        json.dumps({"about": about, "places": result}, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    total = sum(len(h) for h in result.values())
    with_photo = sum(1 for hs in result.values() for h in hs if h.get("photo"))
    print(f"{len(result)} places, {total} hotels, {with_photo} with a photo")


if __name__ == "__main__":
    main()
