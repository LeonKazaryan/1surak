"""What a hotel with a live offer shows: its photos (the booked room's first), the room as the hotel names it with
its size, beds, view and the amenities worth a glance, what guests rate the hotel for, and where the price is from.

The provider speaks English: views, beds, amenities and the guests' categories are said in Russian from a fixed
list, and anything not on it is left out rather than half translated.
"""

import re

from app.hotels.liteapi import Room
from app.plan.hotels import Hotel, Rate

PHOTOS = 14
AMENITY_CHIPS = 6
VIEWS = {
    "sea view": "вид на море",
    "ocean view": "вид на океан",
    "partial sea view": "частичный вид на море",
    "partial ocean view": "частичный вид на океан",
    "panoramic sea view": "панорамный вид на море",
    "beach view": "вид на пляж",
    "bay view": "вид на залив",
    "lagoon view": "вид на лагуну",
    "lake view": "вид на озеро",
    "river view": "вид на реку",
    "mountain view": "вид на горы",
    "city view": "вид на город",
    "landmark view": "вид на достопримечательности",
    "garden view": "вид на сад",
    "park view": "вид на парк",
    "pool view": "вид на бассейн",
    "courtyard view": "вид во двор",
    "inner courtyard view": "вид во двор",
    "street view": "вид на улицу",
}
AMENITIES: tuple[tuple[re.Pattern, str], ...] = tuple(
    (re.compile(pattern, re.IGNORECASE), label)
    for pattern, label in (
        (r"^(?!.*or shower).*(bath\s*tub|\bbath$)", "ванна"),
        (r"hot tub|spa tub|jacuzzi|whirlpool", "джакузи"),
        (r"balcony", "балкон"),
        (r"terrace|patio", "терраса"),
        (r"private pool|plunge pool", "свой бассейн"),
        (r"kitchen", "кухня"),
        (r"washing machine", "стиральная машина"),
        (r"^air conditioning$", "кондиционер"),
        (r"^free wi-?fi$", "Wi-Fi"),
        (r"soundproof", "шумоизоляция"),
        (r"coffee machine|espresso|coffee/tea maker", "кофе и чай"),
        (r"^minibar$", "мини-бар"),
        (r"^refrigerator$|^mini-fridge$", "холодильник"),
        (r"sofa bed", "диван-кровать"),
        (r"^(?!no ).*(cribs?|cots)\b", "детская кроватка"),
        (r"interconnected", "смежные номера"),
    )
)
# (one, two to four, five and more)
BEDS = {
    "single": ("односпальная кровать", "односпальные кровати", "односпальных кроватей"),
    "double": ("двуспальная кровать", "двуспальные кровати", "двуспальных кроватей"),
    "sofa": ("диван-кровать", "диван-кровати", "диван-кроватей"),
    "bunk": ("двухъярусная кровать", "двухъярусные кровати", "двухъярусных кроватей"),
    "futon": ("футон", "футона", "футонов"),
}
BED_KINDS = (("sofa", "sofa"), ("bunk", "bunk"), ("futon", "futon"), ("twin", "single"), ("single", "single"))
SCORES = (
    ("Location", "Расположение"),
    ("Cleanliness", "Чистота"),
    ("Service", "Сервис"),
    ("Room Quality", "Номера"),
    ("Food and Beverage", "Еда"),
)
SHOWN_SCORES = 4


def _form(n: int, forms: tuple[str, str, str]) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return forms[0]
    return forms[1] if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else forms[2]


def beds_text(beds: tuple[tuple[int, str], ...]) -> str | None:
    """«1 двуспальная кровать», «2 односпальные кровати + диван-кровать»."""
    parts = []
    for count, kind in beds:
        name = kind.casefold()
        key = next((k for word, k in BED_KINDS if word in name), "double" if "bed" in name else None)
        if key:
            parts.append(f"{count} {_form(count, BEDS[key])}")
    return " + ".join(parts) or None


def view_text(room: Room | None) -> str | None:
    return next((VIEWS[v.casefold()] for v in room.views if v.casefold() in VIEWS), None) if room else None


def amenity_chips(room: Room | None) -> list[str]:
    if room is None:
        return []
    chips = dict.fromkeys(label for a in room.amenities for pattern, label in AMENITIES if pattern.search(a))
    return list(chips)[:AMENITY_CHIPS]


def live_card(h: Hotel, rate: Rate) -> dict:
    """The live offer's part of a hotel card; {} for a hotel without one."""
    if not h.provider:
        return {}
    room: Room | None = h.rooms.get(rate.room_id or "")
    room_photos = room.photos if room else ()
    named = dict(h.scores)
    return {
        "photos": list(dict.fromkeys([*room_photos, *h.gallery]))[:PHOTOS],
        "room": {
            "name": rate.room or (room.name if room else None),
            "size_m2": room.size_m2 if room else None,
            "beds": beds_text(room.beds) if room else None,
            "view": view_text(room),
            "amenities": amenity_chips(room),
            "photos": min(len(room_photos), PHOTOS),  # the first ones of `photos` are of this room
        }
        if rate.room or room
        else None,
        "scores": [
            {"label": label, "score": round(named[name], 1)} for name, label in SCORES if name in named
        ][:SHOWN_SCORES],
        "cancel_until": rate.cancel_until.isoformat() if rate.cancel_until else None,
        "price_source": h.provider,
        "sandbox": h.sandbox,
    }
