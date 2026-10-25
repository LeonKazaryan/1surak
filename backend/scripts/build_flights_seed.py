"""Builds the offline Travelpayouts dictionaries: airlines, cities with an airport, and the route map.

Run: cd backend && python -m scripts.build_flights_seed  (needs internet, a few seconds)
Prices stay online; names, coordinates and routes change rarely, so the app needs no network for them.
Re-run it every week or two: airlines open and close routes (see app/flights/network.py).
"""

import json
from pathlib import Path

import httpx

DATA = "https://api.travelpayouts.com/data/ru/{}.json"
ROUTES = "https://api.travelpayouts.com/data/routes.json"
# Codes Travelpayouts has renamed while its route list and our catalogue still use the old one.
RENAMED = {"FRU": "BSZ"}  # Bishkek
OUT = Path(__file__).resolve().parent.parent / "app" / "flights" / "seed"


def fetch(name: str, url: str = DATA) -> list[dict]:
    response = httpx.get(url.format(name), timeout=120)
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
    known = {c["code"] for c in cities}
    # only airports whose code differs from their city's: SVO > MOW; AYT is both, so it needs no row
    airports = {
        a["code"]: a["city_code"]
        for a in fetch("airports")
        if a.get("code") and a.get("city_code") in known and a["code"] != a["city_code"]
    }
    airports.update({old: new for old, new in RENAMED.items() if new in known})
    routes = build_routes(fetch("routes", ROUTES), airports, known)
    for name, data in (
        ("cities", cities),
        ("airlines", airlines),
        ("airports", airports),
        ("routes", routes),
    ):
        (OUT / f"{name}.json").write_text(
            json.dumps(
                data, ensure_ascii=False, separators=(",", ":"), sort_keys=name in ("airports", "routes")
            ),
            encoding="utf-8",
        )
    links = sum(len(d) for d in routes.values())
    print(f"{len(cities)} cities, {len(airlines)} airlines, {len(airports)} airports, {links} direct links")


def build_routes(rows: list[dict], airports: dict[str, str], known: set[str]) -> dict[str, dict[str, str]]:
    """Airline routes > direct city-to-city links: {"MOW": {"IST": "PC SU TK"}}, operating airlines only."""
    found: dict[str, dict[str, set[str]]] = {}
    for r in rows:
        if r.get("transfers") or r.get("codeshare"):
            continue
        origin = airports.get(r["departure_airport_iata"], r["departure_airport_iata"])
        destination = airports.get(r["arrival_airport_iata"], r["arrival_airport_iata"])
        if origin in known and destination in known and origin != destination:
            found.setdefault(origin, {}).setdefault(destination, set()).add(r.get("airline_iata") or "")
    return {
        o: {d: " ".join(sorted(a for a in carriers if a)) for d, carriers in ds.items()}
        for o, ds in found.items()
    }


if __name__ == "__main__":
    main()
