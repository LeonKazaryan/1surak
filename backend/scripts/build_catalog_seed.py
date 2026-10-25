"""Builds the committed catalogue seed. Run on a dev machine, never inside the container:

    cd backend && python -m scripts.build_catalog_seed

1. Resolves each curated place to a Wikidata QID and coordinates (ru Wikipedia title → QID → P625).
2. Pulls 10 years of daily weather from Open-Meteo and turns it into monthly normals (air, rain days).
3. Pulls daily sea surface temperature for coastal places and turns it into monthly means.
4. Writes app/catalog/seed/places_geo.json and app/catalog/seed/facts.json.

Only stdlib networking, so it needs nothing beyond the app's own requirements.
"""

import hashlib
import json
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError

from app.catalog.catalog import CURATED_PATH, GEO_PATH, SEED_FACTS_PATH
from app.facts.adapters import open_meteo, open_meteo_marine
from app.facts.model import Fact, FactError

USER_AGENT = "beshparmak-1surak/0.1 (https://github.com/ostrovok-hackathon-2026/beshparmak)"
# Open-Meteo's free tier weighs requests by days × variables; 5 years keeps us well inside the hourly limit.
CLIMATE_YEARS = ("2020-01-01", "2024-12-31")
SEA_YEARS = ("2021-01-01", "2024-12-31")
PAUSE_S = 3.0
CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache" / "build_catalog_seed"


def get_json(url: str, params: dict, cache: bool = False, pause_s: float = PAUSE_S) -> dict:
    full_url = f"{url}?{urllib.parse.urlencode(params)}"
    cached = CACHE_DIR / f"{hashlib.sha256(full_url.encode()).hexdigest()[:24]}.json"
    if cache and cached.exists():
        return json.loads(cached.read_text(encoding="utf-8"))
    request = urllib.request.Request(full_url, headers={"User-Agent": USER_AGENT})
    for attempt in range(6):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                data = json.load(response)
            break
        except OSError as error:
            if attempt == 5:
                raise
            wait = 65 if isinstance(error, HTTPError) and error.code == 429 else 5 * (attempt + 1)
            print(f"  [{error}, waiting {wait}s]", end="", flush=True)
            time.sleep(wait)
    if cache:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cached.write_text(json.dumps(data), encoding="utf-8")
        time.sleep(pause_s)  # only pause after real network calls
    return data


def resolve_geo(places: list[dict]) -> dict[str, dict]:
    titles = [p["wiki_ru"] for p in places]
    qids: dict[str, str] = {}
    for start in range(0, len(titles), 50):
        batch = titles[start : start + 50]
        data = get_json(
            "https://www.wikidata.org/w/api.php",
            {
                "action": "wbgetentities",
                "sites": "ruwiki",
                "titles": "|".join(batch),
                "props": "sitelinks",
                "sitefilter": "ruwiki",
                "format": "json",
            },
        )
        if "error" in data:
            sys.exit(f"Wikidata error: {data['error'].get('info')}")
        for qid, entity in data["entities"].items():
            if qid.startswith("Q"):
                qids[entity["sitelinks"]["ruwiki"]["title"]] = qid

    values = " ".join(f"wd:{q}" for q in qids.values())
    sparql = f"SELECT ?item ?coord WHERE {{ VALUES ?item {{ {values} }} ?item wdt:P625 ?coord. }}"
    rows = get_json("https://query.wikidata.org/sparql", {"query": sparql, "format": "json"})["results"][
        "bindings"
    ]
    coords: dict[str, tuple[float, float]] = {}
    for row in rows:
        qid = row["item"]["value"].rsplit("/", 1)[-1]
        lon, lat = row["coord"]["value"].removeprefix("Point(").removesuffix(")").split()
        coords.setdefault(qid, (round(float(lat), 4), round(float(lon), 4)))

    geo: dict[str, dict] = {}
    for place in places:
        qid = qids.get(place["wiki_ru"])
        if qid is None or qid not in coords:
            sys.exit(
                f"Could not resolve {place['id']!r} (ru title {place['wiki_ru']!r}) to a QID with coordinates"
            )
        lat, lon = coords[qid]
        geo[place["id"]] = {"qid": qid, "lat": lat, "lon": lon}
    return geo


def climate_facts(qid: str, lat: float, lon: float, fetched_at: datetime) -> list[Fact]:
    payload = get_json(
        "https://archive-api.open-meteo.com/v1/archive",
        {
            "latitude": lat,
            "longitude": lon,
            "start_date": CLIMATE_YEARS[0],
            "end_date": CLIMATE_YEARS[1],
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
            "timezone": "auto",
        },
        cache=True,
    )
    return open_meteo.monthly_climate(qid, payload, fetched_at)


def sea_facts(qid: str, lat: float, lon: float, fetched_at: datetime) -> list[Fact]:
    payload = get_json(
        "https://marine-api.open-meteo.com/v1/marine",
        {
            "latitude": lat,
            "longitude": lon,
            "start_date": SEA_YEARS[0],
            "end_date": SEA_YEARS[1],
            "daily": open_meteo_marine.VARIABLE,
        },
        cache=True,
    )
    return open_meteo_marine.monthly_sea_temp(qid, payload, fetched_at)


def to_json(fact: Fact) -> dict:
    row = asdict(fact)
    if isinstance(row["value"], float):
        row["value"] = round(row["value"], 1)
    for key in ("fetched_at", "valid_until"):
        row[key] = row[key].isoformat() if row[key] else None
    return row


def main() -> None:
    curated = json.loads(CURATED_PATH.read_text(encoding="utf-8"))
    places = curated["places"]
    fetched_at = datetime.now(UTC).replace(microsecond=0)

    print(f"Resolving {len(places)} places on Wikidata…")
    geo = resolve_geo(places)
    write(GEO_PATH, geo)

    facts: list[dict] = []
    for place in places:
        g = geo[place["id"]]
        print(f"{place['id']:16} {g['qid']:10} {g['lat']:9} {g['lon']:9}", end="", flush=True)
        rows = climate_facts(g["qid"], g["lat"], g["lon"], fetched_at)
        if "sea" in place["kinds"]:
            # a city centre can snap to a land cell of the marine model; sea_point overrides it
            sea_lat, sea_lon = place.get("sea_point") or (g["lat"], g["lon"])
            try:
                sea = sea_facts(g["qid"], sea_lat, sea_lon, fetched_at)
            except FactError as error:
                sea = []
                print(f"  sea failed: {error}", end="")
            if len(sea) < 12:
                print(f"  WARNING: sea_temp for {len(sea)} months only", end="")
            rows += sea
        print(f"  {len(rows)} facts")
        facts += [to_json(f) for f in rows]

    write(SEED_FACTS_PATH, facts)
    print(f"Wrote {len(facts)} facts to {SEED_FACTS_PATH}")


def write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
