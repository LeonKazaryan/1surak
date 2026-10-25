"""Builds the offline Travelpayouts dictionaries: airlines, and the cities that have an airport.

Run: cd backend && python -m scripts.build_flights_seed  (needs internet, a few seconds)
Prices stay online; these names and coordinates change rarely, so the app needs no network for them.
"""

import json
from pathlib import Path

import httpx

DATA = "https://api.travelpayouts.com/data/ru/{}.json"
OUT = Path(__file__).resolve().parent.parent / "app" / "flights" / "seed"


def fetch(name: str) -> list[dict]:
    response = httpx.get(DATA.format(name), timeout=60)
    response.raise_for_status()
    return response.json()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    countries = {c["code"]: c["name"] for c in fetch("countries") if c.get("name")}
    cities = [
        {
            "code": c["code"],
            "name": c["name"],
            "country": countries.get(c["country_code"], c["country_code"]),
            "lat": round(c["coordinates"]["lat"], 3),
            "lon": round(c["coordinates"]["lon"], 3),
            "from": (c.get("cases") or {}).get("ro"),  # «из Астаны»
        }
        for c in fetch("cities")
        if c.get("has_flightable_airport") and c.get("name") and c.get("coordinates")
    ]
    airlines = {
        a["code"]: a.get("name") or (a.get("name_translations") or {}).get("en")
        for a in fetch("airlines")
        if a.get("code") and (a.get("name") or (a.get("name_translations") or {}).get("en"))
    }
    (OUT / "cities.json").write_text(
        json.dumps(cities, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    (OUT / "airlines.json").write_text(
        json.dumps(airlines, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    print(f"{len(cities)} cities, {len(airlines)} airlines")


if __name__ == "__main__":
    main()
