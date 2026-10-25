"""Time zones and airport coordinates for every catalogue place: app/plan/seed/places.json.

    cd backend && .venv/bin/python -m scripts.build_plan_seed

Airports come from OurAirports (public domain). Time zones are ours, one IANA name per place.
"""

import csv
import io
import json
from pathlib import Path

import httpx

from app.catalog.catalog import load_catalog
from app.plan.places import SEED_PATH

AIRPORTS_URL = "https://davidmegginson.github.io/ourairports-data/airports.csv"
USER_AGENT = "1surak-hackathon/0.1 (https://github.com/ostrovok-hackathon-2026/beshparmak)"

ZONES = {
    "sochi": "Europe/Moscow",
    "anapa": "Europe/Moscow",
    "kaliningrad": "Europe/Kaliningrad",
    "kazan": "Europe/Moscow",
    "spb": "Europe/Moscow",
    "nizhny": "Europe/Moscow",
    "suzdal": "Europe/Moscow",
    "altai": "Asia/Barnaul",
    "baikal": "Asia/Irkutsk",
    "dagestan": "Europe/Moscow",
    "kamchatka": "Asia/Kamchatka",
    "murmansk": "Europe/Moscow",
    "karelia": "Europe/Moscow",
    "kislovodsk": "Europe/Moscow",
    "elbrus": "Europe/Moscow",
    "sheregesh": "Asia/Novokuznetsk",
    "vladivostok": "Asia/Vladivostok",
    "antalya": "Europe/Istanbul",
    "alanya": "Europe/Istanbul",
    "bodrum": "Europe/Istanbul",
    "istanbul": "Europe/Istanbul",
    "hurghada": "Africa/Cairo",
    "sharm": "Africa/Cairo",
    "dubai": "Asia/Dubai",
    "abu_dhabi": "Asia/Dubai",
    "ras_al_khaimah": "Asia/Dubai",
    "phuket": "Asia/Bangkok",
    "pattaya": "Asia/Bangkok",
    "bangkok": "Asia/Bangkok",
    "nha_trang": "Asia/Ho_Chi_Minh",
    "phu_quoc": "Asia/Ho_Chi_Minh",
    "sri_lanka": "Asia/Colombo",
    "maldives": "Indian/Maldives",
    "bali": "Asia/Makassar",
    "sanya": "Asia/Shanghai",
    "beijing": "Asia/Shanghai",
    "tbilisi": "Asia/Tbilisi",
    "batumi": "Asia/Tbilisi",
    "yerevan": "Asia/Yerevan",
    "baku": "Asia/Baku",
    "samarkand": "Asia/Samarkand",
    "almaty": "Asia/Almaty",
    "issyk_kul": "Asia/Bishkek",
    "minsk": "Europe/Minsk",
    "varadero": "America/Havana",
    "monastir": "Africa/Tunis",
    "seychelles": "Indian/Mahe",
    "mauritius": "Indian/Mauritius",
    "zanzibar": "Africa/Dar_es_Salaam",
    "muscat": "Asia/Muscat",
    "goa": "Asia/Kolkata",
    "belgrade": "Europe/Belgrade",
    "budva": "Europe/Podgorica",
}
# Resort islands are reached by boat or seaplane, not by road.
BY_BOAT = {"maldives"}


# OurAirports lists Manas under its new code BSZ and Gorno-Altaysk without scheduled service: match by ICAO.
BY_ICAO = {"FRU": "UCFM", "RGK": "UNBG"}


def airport_coordinates(codes: set[str]) -> dict[str, list[float]]:
    text = httpx.get(AIRPORTS_URL, headers={"User-Agent": USER_AGENT}, timeout=60).text
    icao = {BY_ICAO[c]: c for c in codes if c in BY_ICAO}
    found = {}
    for row in csv.DictReader(io.StringIO(text)):
        code = row["iata_code"] if row["scheduled_service"] == "yes" else None
        code = icao.get(row["icao_code"]) or (code if code in codes and code not in BY_ICAO else None)
        if code:
            found[code] = [round(float(row["latitude_deg"]), 4), round(float(row["longitude_deg"]), 4)]
    return found


def main() -> None:
    catalog = load_catalog()
    missing_zones = {p.id for p in catalog.places} - ZONES.keys()
    if missing_zones:
        raise SystemExit(f"No time zone for {sorted(missing_zones)}")
    codes = {p.airport for p in catalog.places if p.airport}
    coords = airport_coordinates(codes)
    places = {}
    for place in catalog.places:
        entry: dict = {"tz": ZONES[place.id]}
        if place.airport and place.airport in coords:
            entry["airport"] = {
                "code": place.airport,
                "lat": coords[place.airport][0],
                "lon": coords[place.airport][1],
            }
        if place.id in BY_BOAT:
            entry["transfer"] = "boat"
        places[place.id] = entry
    seed = {
        "about": "Airport coordinates from OurAirports (public domain); time zones by the 1surak team.",
        "places": places,
    }
    Path(SEED_PATH).parent.mkdir(parents=True, exist_ok=True)
    Path(SEED_PATH).write_text(json.dumps(seed, ensure_ascii=False, indent=1) + "\n")
    print(f"{len(places)} places, {sum('airport' in p for p in places.values())} with airport coordinates")
    lost = sorted(codes - coords.keys())
    if lost:
        print("No coordinates for", lost)


if __name__ == "__main__":
    main()
