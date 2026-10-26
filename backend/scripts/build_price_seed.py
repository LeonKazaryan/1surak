"""Builds the countries' price levels: how dear a country is next to the US (1.0), for prices we estimate.

Run: cd backend && python -m scripts.build_price_seed  (needs internet, a few seconds)
The World Bank's PPP conversion factor (PA.NUS.PPP, local currency per international dollar) over the market
exchange rate (PA.NUS.FCRF, local currency per US dollar), the latest year each country has: the «price level
ratio». Licence CC BY 4.0. A taxi kilometre where no fare was found costs a US kilometre times this.
"""

import json
from pathlib import Path

import httpx

API = "https://api.worldbank.org/v2/country/all/indicator/{}?format=json&mrnev=1&per_page=400"
OUT = Path(__file__).resolve().parent.parent / "app" / "plan" / "seed" / "price_levels.json"


def latest(indicator: str) -> dict[str, float]:
    response = httpx.get(API.format(indicator), timeout=120)
    response.raise_for_status()
    _, rows = response.json()
    return {r["country"]["id"]: r["value"] for r in rows if r.get("value") and len(r["country"]["id"]) == 2}


def main() -> None:
    ppp, fx = latest("PA.NUS.PPP"), latest("PA.NUS.FCRF")
    levels = {code: round(ppp[code] / fx[code], 3) for code in sorted(ppp.keys() & fx.keys()) if fx[code] > 0}
    OUT.write_text(json.dumps(levels, separators=(",", ":"), sort_keys=True), encoding="utf-8")
    print(f"{len(levels)} countries, US {levels.get('US')}, KZ {levels.get('KZ')}, GB {levels.get('GB')}")


if __name__ == "__main__":
    main()
