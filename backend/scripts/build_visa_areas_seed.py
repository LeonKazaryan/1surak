"""Builds the visa areas: groups of countries one visa opens together, so a route through Italy, Spain and
Portugal needs one Schengen visa, not three.

Run: cd backend && python -m scripts.build_visa_areas_seed  (needs internet, a few seconds)
The members are Wikidata's (CC0): the countries «member of» (P463) the area with no end date, by ISO code. A
member stated as a constituent country (the Netherlands) takes the code of its state. Re-run it when an area
grows: Bulgaria and Romania joined Schengen in 2024-2025.
"""

import json
from pathlib import Path

import httpx

SPARQL = "https://query.wikidata.org/sparql"
HEADERS = {"User-Agent": "1surak/1.0 (https://github.com/ostrovok-hackathon-2026/beshparmak)"}
OUT = Path(__file__).resolve().parent.parent / "app" / "visas" / "seed" / "areas.json"
# Wikidata item > how the chip names the area and the visa it shares
AREAS = {"Q1969730": {"id": "schengen", "name": "Шенген", "visa": "шенгенская виза"}}
QUERY = """SELECT DISTINCT ?iso WHERE {{
  ?member p:P463 ?statement . ?statement ps:P463 wd:{area} .
  FILTER NOT EXISTS {{ ?statement pq:P582 ?ended }}
  OPTIONAL {{ ?member wdt:P297 ?own }}
  OPTIONAL {{ ?member wdt:P17 ?state . ?state wdt:P297 ?states }}
  BIND(COALESCE(?own, ?states) AS ?iso)
  FILTER(BOUND(?iso))
}}"""


def members(area: str) -> list[str]:
    response = httpx.get(
        SPARQL, params={"query": QUERY.format(area=area), "format": "json"}, headers=HEADERS, timeout=60
    )
    response.raise_for_status()
    return sorted({row["iso"]["value"] for row in response.json()["results"]["bindings"]})


def main() -> None:
    areas = {area["id"]: {**area, "members": members(qid)} for qid, area in AREAS.items()}
    for area in areas.values():
        del area["id"]
    OUT.write_text(json.dumps(areas, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    for key, area in areas.items():
        print(key, len(area["members"]), " ".join(area["members"]))


if __name__ == "__main__":
    main()
