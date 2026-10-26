"""Builds the offline visa rules: what a passport needs for every country, and the countries' names.

Run: cd backend && python -m scripts.build_visa_seed  (needs internet, a few seconds)
- Rules: the Passport Index dataset (github.com/imorte/passport-index-data, MIT, scraped from passportindex.org),
  199 passports × 199 destinations: visa free (with days), visa on arrival, eTA, e-visa, visa required,
  no admission. Re-run it every month or two: visa regimes change.
- Names: Travelpayouts' country list in Russian with its cases («граждан Казахстана», «в США») and in English
  (the web searches for a visa fee are in English).
"""

import json
from pathlib import Path

import httpx

PASSPORT_INDEX = "https://raw.githubusercontent.com/imorte/passport-index-data/main/passport-index.json"
COUNTRIES = "https://api.travelpayouts.com/data/{}/countries.json"
OUT = Path(__file__).resolve().parent.parent / "app" / "visas" / "seed"
# The dataset's statuses, as the short codes the seed stores; days follow after a colon: «vf:30».
STATUSES = {
    "visa free": "vf",
    "visa on arrival": "voa",
    "eta": "eta",
    "e-visa": "ev",
    "visa required": "vr",
    "no admission": "na",
}


def fetch(url: str):
    response = httpx.get(url, timeout=120, follow_redirects=True)
    response.raise_for_status()
    return response.json()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rules: dict[str, dict[str, str]] = {}
    for passport, destinations in fetch(PASSPORT_INDEX).items():
        for destination, entry in destinations.items():
            code = STATUSES.get(entry.get("status"))
            if code is None:  # -1: the passport's own country
                continue
            days = entry.get("days")
            rules.setdefault(passport.upper(), {})[destination.upper()] = f"{code}:{days}" if days else code
    english = {c["code"]: c.get("name") for c in fetch(COUNTRIES.format("en"))}
    countries = {
        c["code"]: {
            "name": c["name"],
            "en": english.get(c["code"]) or c["name"],
            "cases": c.get("cases") or {},
        }
        for c in fetch(COUNTRIES.format("ru"))
        if c.get("code") and c.get("name")
    }
    for name, data in (("passport_index", rules), ("countries", countries)):
        (OUT / f"{name}.json").write_text(
            json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True), encoding="utf-8"
        )
    pairs = sum(len(d) for d in rules.values())
    print(f"{len(rules)} passports, {pairs} rules, {len(countries)} country names")


if __name__ == "__main__":
    main()
