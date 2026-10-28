"""Regions the user names («по Европе», «в Азию»), as every country in them, not only the catalogue's.

By ISO code, roughly the UN's regions: Belarus counts as Europe, the Caucasus is its own, and Turkey is not
Europe (Antalya is in Asia; «в Турцию» names the country itself). Russia is never «abroad» here: domestic trips have their own filter.
The names returned are the ones search compares: the catalogue's own spelling where it has the country
(«ОАЭ»), Travelpayouts' elsewhere.
"""

from functools import cache

from app.catalog.catalog import load_catalog
from app.flights.dictionary import cities

EUROPE = {
    "AL",
    "AD",
    "AT",
    "BY",
    "BE",
    "BA",
    "BG",
    "HR",
    "CY",
    "CZ",
    "DK",
    "EE",
    "FI",
    "FR",
    "DE",
    "GR",
    "HU",
    "IS",
    "IE",
    "IT",
    "XK",
    "LV",
    "LI",
    "LT",
    "LU",
    "MT",
    "MD",
    "MC",
    "ME",
    "NL",
    "MK",
    "NO",
    "PL",
    "PT",
    "RO",
    "SM",
    "RS",
    "SK",
    "SI",
    "ES",
    "SE",
    "CH",
    "UA",
    "GB",
    "VA",
}
BALKANS = {"AL", "BA", "BG", "HR", "ME", "MK", "RS", "SI", "XK", "GR"}
CAUCASUS = {"GE", "AM", "AZ"}
CENTRAL_ASIA = {"KZ", "UZ", "KG", "TJ", "TM"}
SOUTHEAST_ASIA = {"TH", "VN", "ID", "MY", "SG", "PH", "KH", "LA", "MM", "BN", "TL"}
ASIA = SOUTHEAST_ASIA | {"CN", "JP", "KR", "MN", "IN", "LK", "MV", "NP", "BD", "PK", "BT", "TW", "HK", "MO"}
MIDDLE_EAST = {"AE", "OM", "QA", "BH", "KW", "SA", "JO", "IL", "LB", "IQ", "IR"}
MAGHREB = {"MA", "DZ", "TN"}
NORTH_AFRICA = MAGHREB | {"EG", "LY"}
AFRICA = {
    "EG",
    "TN",
    "MA",
    "DZ",
    "LY",
    "ZA",
    "TZ",
    "KE",
    "SC",
    "MU",
    "MG",
    "NA",
    "ET",
    "GH",
    "NG",
    "SN",
    "CV",
    "UG",
    "RW",
    "ZW",
    "ZM",
    "BW",
    "MZ",
    "CI",
    "CM",
    "AO",
    "RE",
}
AMERICAS = {
    "US",
    "CA",
    "MX",
    "CU",
    "DO",
    "JM",
    "BS",
    "BR",
    "AR",
    "CL",
    "PE",
    "CO",
    "EC",
    "BO",
    "UY",
    "PY",
    "VE",
    "CR",
    "PA",
    "GT",
    "HN",
    "NI",
    "SV",
    "BZ",
}

# the words people use, matched as a substring of what they said: «по Европе» holds «европ»
REGIONS: dict[str, set[str]] = {
    "европ": EUROPE,
    "балкан": BALKANS,
    "кавказ": CAUCASUS,
    "закавказ": CAUCASUS,
    "средн азия": CENTRAL_ASIA,
    "средняя азия": CENTRAL_ASIA,
    "центральн азия": CENTRAL_ASIA,
    "центральная азия": CENTRAL_ASIA,
    "юго-восточн": SOUTHEAST_ASIA,
    "ближн восток": MIDDLE_EAST,
    "ближний восток": MIDDLE_EAST,
    "магриб": MAGHREB,
    "северная африк": NORTH_AFRICA,
    "северной африк": NORTH_AFRICA,
    "северную африк": NORTH_AFRICA,
    "африк": AFRICA,  # after its parts: «северная африка» is matched first
    "америк": AMERICAS,
    "ази": ASIA,  # last: «юго-восточная азия» and «средняя азия» are matched first
}


@cache
def _names() -> dict[str, set[str]]:
    """Every spelling of each country we may compare against, by ISO code."""
    found: dict[str, set[str]] = {}
    for c in cities().values():
        if c.country_code:
            found.setdefault(c.country_code, set()).add(c.country)
    for code, country in load_catalog().countries.items():
        found.setdefault(code, set()).add(country.name)
    return found


def region_codes(text: str) -> set[str] | None:
    needle = text.casefold().replace("ё", "е")
    return next((codes for key, codes in REGIONS.items() if key in needle), None)


def country_names(text: str) -> list[str] | None:
    """Every spelling of the one country the text names («Германия», «ОАЭ»), or None."""
    needle = text.strip().casefold()
    for names in _names().values():
        if needle in {n.casefold() for n in names}:
            return sorted(names)
    return None


def country_code(text: str) -> str | None:
    """The ISO code of the one country the text names («Казахстан» → KZ), or None."""
    needle = text.strip().casefold()
    return next((code for code, names in _names().items() if needle in {n.casefold() for n in names}), None)


def countries_in(text: str) -> list[str] | None:
    """The country names of the region the text names, or None when it names no region."""
    codes = region_codes(text)
    if codes is None:
        return None
    return sorted({name for code in codes for name in _names().get(code, ())})
