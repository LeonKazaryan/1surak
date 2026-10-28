"""The trip as the chat's header shows it: where, when, who, the budget and from where, as typed fields.

The header is the brief made visible: it fills in as the agent understands the request, and every field is
there to be changed. The chips under the cards (app.trip.brief.chips) say the same in plain words.
"""

from app.catalog.catalog import KIND_LABELS, load_catalog
from app.catalog.search import MONTHS
from app.destinations.regions import country_code
from app.flights import city
from app.flights.dictionary import cities, find_city
from app.money import CURRENCIES
from app.photos import place_photo
from app.trip.brief import BUDGET_LABELS, TripBrief, _travelers, night_range, plural


def _middle(points: list[tuple[float, float]]) -> tuple[float, float] | None:
    if not points:
        return None
    return sum(p[0] for p in points) / len(points), sum(p[1] for p in points) / len(points)


def _destination(text: str) -> dict:
    """The place or country the user named, with its flag, a point for the map and a photo when we have one."""
    catalog = load_catalog()
    place = catalog.find(text)
    found = None if place else find_city(text)
    code = place.country.code if place else country_code(text) or (found.country_code if found else None)
    photo = place_photo(place.id) if place else None
    if photo is None and code:  # a country: the photo of its first place that has one
        photo = next(
            (p for p in (place_photo(p.id) for p in catalog.places if p.country.code == code) if p), None
        )
    if place or found:
        at = (place.lat, place.lon) if place else (found.lat, found.lon)
    else:  # a country: the middle of its catalogue places, else of its cities with an airport
        at = _middle([(p.lat, p.lon) for p in catalog.places if p.country.code == code]) or _middle(
            [(c.lat, c.lon) for c in cities().values() if code and c.country_code == code]
        )
    return {
        "name": text,
        "country_code": code,
        "place_id": place.id if place else None,
        "photo": photo,
        "lat": round(at[0], 3) if at else None,
        "lon": round(at[1], 3) if at else None,
    }


def _when(b: TripBrief) -> str | None:
    parts = []
    if b.date_from and b.date_to:
        parts.append(f"{b.date_from:%d.%m}–{b.date_to:%d.%m}")
    elif b.month:
        parts.append(MONTHS[b.month - 1].capitalize())
    low, high = night_range(b)
    if low:
        span = f"{low}–{high}" if high != low else f"{low}"
        parts.append(f"{span} {plural(high or low, ('ночь', 'ночи', 'ночей'))}")
    return " · ".join(parts) or None


def passport(b: TripBrief) -> dict:
    """What the agent knows about the trip, field by field; None where it does not know yet."""
    # the city the user named or picked, else the one the tickets on the cards were found from
    home = city(b.origin_code or b.priced_from) if (b.origin_code or b.priced_from) else None
    if b.budget_total:
        budget = f"до {CURRENCIES[b.budget_currency or 'RUB'].amount(b.budget_total)}"
    else:
        budget = BUDGET_LABELS.get(b.budget_level) if b.budget_level is not None else None
    return {
        "destination": _destination(b.destination) if b.destination else None,
        "kinds": [{"kind": k, "label": KIND_LABELS[k]} for k in b.kinds or []],
        "month": b.month,
        "when": _when(b),
        "travelers": _travelers(b),
        "budget": budget,
        "origin": (
            {"code": home.code, "name": home.name, "from": home.from_text, "lat": home.lat, "lon": home.lon}
            if home
            else None
        ),
        "multi_city": bool(b.multi_city),
        "multi_country": bool(b.multi_country),
        "visa_free_only": bool(b.visa_free_only),
        "by_land": bool(b.by_land),
        "wishes": list(b.wishes or []),
    }
