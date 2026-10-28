"""Builds how well known each city with an airport is: in how many Wikipedias its article exists.

Run: cd backend && python -m scripts.build_fame_seed  (needs internet, a few seconds)
One Wikidata query: every airport with an IATA code (P238), the place it serves (P931), that place's number of
sitelinks and where it is. Folded to the Travelpayouts city (SVO > MOW), the best known place within NEAR_KM of
the city wins: Paris Vatry serves Paris, but its city is Châlons. Wikidata is CC0.
Routes rank Marrakech (142) and Fes (124) before Nador (53): the route map's count of direct flights misses
the low-cost airlines most of Morocco flies on.
"""

import json
from pathlib import Path

import httpx

from app.flights.dictionary import City, cities, city_code, distance_km

SPARQL = "https://query.wikidata.org/sparql"
QUERY = """SELECT ?iata ?links ?lat ?lon WHERE {
  ?airport wdt:P238 ?iata ; wdt:P931 ?place .
  ?place wikibase:sitelinks ?links ; p:P625/psv:P625 [wikibase:geoLatitude ?lat ; wikibase:geoLongitude ?lon] .
}"""
NEAR_KM = 60  # Paris Vatry serves Paris, 150 km away: its own city (Châlons) is not Paris
HEADERS = {"User-Agent": "1surak/1.0 (https://github.com/ostrovok-hackathon-2026/beshparmak)"}
OUT = Path(__file__).resolve().parent.parent / "app" / "flights" / "seed" / "fame.json"


def main() -> None:
    response = httpx.get(SPARQL, params={"query": QUERY, "format": "json"}, headers=HEADERS, timeout=120)
    response.raise_for_status()
    known = cities()
    fame: dict[str, int] = {}
    for row in response.json()["results"]["bindings"]:
        code = city_code(row["iata"]["value"])
        here = known.get(code)
        if here is None:
            continue
        # the place the airport serves counts only when it is that city: not a capital a long bus ride away
        there = City("", "", "", float(row["lat"]["value"]), float(row["lon"]["value"]))
        if distance_km(here, there) <= NEAR_KM:
            fame[code] = max(fame.get(code, 0), int(row["links"]["value"]))
    OUT.write_text(json.dumps(dict(sorted(fame.items())), separators=(",", ":")), encoding="utf-8")
    print(
        f"{len(fame)} of {len(known)} cities, LON {fame.get('LON')}, RAK {fame.get('RAK')}, NDR {fame.get('NDR')}"
    )


if __name__ == "__main__":
    main()
