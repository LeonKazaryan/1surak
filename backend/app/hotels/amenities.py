"""The guest's hotel wishes read in the provider's own data: the room a rate sells (its name, view and amenities),
the rate's meal plan and refund, the hotel's facilities and its pets rule.

A wish this vocabulary knows is answered at once for every hotel, with the words of the data that prove it, and
the rates are cut to the rooms that fit the most wishes, so the plan books the room the guest asked for. What the
data does not say stays «unknown», never a guess; the web check (evidence.py) takes the wishes it does not know.
"""

import re
from dataclasses import dataclass
from typing import Literal

from app.hotels.liteapi import Details, Room
from app.plan.hotels import LITEAPI, MEAL_LABELS, Evidence, Rate, Verdict

Scope = Literal["room", "rate", "hotel", "pets"]
LISTED_AMENITIES = 5  # a room whose amenities are listed this fully and lack the wish does not have it
ANY_VIEW = re.compile(r"\bview\b|\bno window\b", re.IGNORECASE)
PARTIAL = re.compile(r"partial", re.IGNORECASE)
NOT_SAID = "в данных отеля не указано"
NONE_ON_SALE = "на ваши даты таких номеров нет"
OTHER_ROOM = "есть в другом номере"


def _re(pattern: str) -> re.Pattern:
    return re.compile(pattern, re.IGNORECASE)


@dataclass(frozen=True)
class Need:
    key: str
    scope: Scope
    asks: re.Pattern  # how a guest asks for it
    proof: re.Pattern | None = None  # the words in the data that say yes
    not_proof: re.Pattern | None = None  # what looks like it but is not: «Bathtub or shower» is no bath
    meals: frozenset[str] = frozenset()  # rate: the meal plans that fit
    view: bool = False  # a room whose view is known, and is another one, says no
    amenity: bool = False  # a room with its amenities listed, and this one not among them, says no


BOARD_AND_MORE = frozenset({"breakfast", "half_board", "full_board", "all_inclusive"})
# The first need whose words the wish has is the one checked: the narrower ones come first.
NEEDS: tuple[Need, ...] = (
    Need(
        "sea_view",
        "room",
        _re(r"вид\w* на (море|океан|залив|бухту|пляж|воду)|морск\w* вид|sea ?view|ocean ?view"),
        _re(r"(sea|ocean|bay|beach|lagoon|water)\s*-?\s*(view|front)|seaview|oceanview|beachfront"),
        view=True,
    ),
    Need(
        "mountain_view", "room", _re(r"вид\w* на гор|mountain ?view"), _re(r"mountain\s*-?\s*view"), view=True
    ),
    Need(
        "city_view", "room", _re(r"вид\w* на город|city ?view"), _re(r"city\s*-?\s*view|skyline"), view=True
    ),
    Need(
        "bath",
        "room",
        _re(r"ванн(?!ая комн|ой комн)|джакуз|гидромассаж|bath ?tub|jacuzzi"),
        _re(r"bath\s*tub|\bbath\b|hot tub|spa tub|jacuzzi|whirlpool"),
        _re(r"bathtub or shower|shared bath"),
        amenity=True,
    ),
    Need(
        "balcony",
        "room",
        _re(r"балкон|террас|лоджи|balcony|terrace"),
        _re(r"balcon|terrace|patio|lanai|veranda"),
        amenity=True,
    ),
    Need("kitchen", "room", _re(r"кухн|kitchen"), _re(r"kitchen|stovetop|cooktop"), amenity=True),
    Need("aircon", "room", _re(r"кондиционер|air ?condition"), _re(r"air condition"), amenity=True),
    Need(
        "family_room", "room", _re(r"семейн\w* номер|family room"), _re(r"family|connecting|interconnected")
    ),
    Need(
        "crib",
        "room",
        _re(r"детск\w* кроват|кроватк|люльк|\bcrib|\bcots?\b"),
        _re(r"\bcribs?\b|\bcots?\b|infant bed"),
        _re(r"\bno (cribs|cots)"),
    ),
    Need("kids_pool", "hotel", _re(r"детск\w* бассейн|kids'? pool"), _re(r"kids'? pool|children'?s pool")),
    Need(
        "pool",
        "hotel",
        _re(r"бассейн|\bpool"),
        _re(r"\bpool\b"),
        _re(r"nearby|table|towel|toys|cover|\bbar\b|umbrella|lounger|kids'? pool|wheelchair|fence"),
    ),
    Need(
        "spa",
        "hotel",
        _re(r"(?<![а-яё])спа(?![а-яё])|сауна|хаммам|\bspa\b"),
        _re(r"\bspa\b|wellness|sauna|hammam|steam room"),
        _re(r"nearby|wheelchair"),
    ),
    # «хороший интернет» is about its speed: the web check reads the guests on it, a facility list cannot
    Need(
        "wifi",
        "hotel",
        _re(r"^(?!.*(хорош|быстр|скорост|fast|good)).*(интернет|wi-?fi|вай-?фай)"),
        _re(r"wi-?fi|internet"),
    ),
    Need("parking", "hotel", _re(r"парковк|parking"), _re(r"parking"), _re(r"offsite|street parking")),
    Need("gym", "hotel", _re(r"фитнес|спортзал|тренаж|\bgym\b|fitness"), _re(r"fitness|\bgym\b")),
    Need("kids_club", "hotel", _re(r"детск\w* клуб|kids'? club"), _re(r"kids'? club|children'?s club")),
    Need("playground", "hotel", _re(r"детск\w* площадк|playground"), _re(r"playground|play area")),
    Need(
        "beach",
        "hotel",
        _re(r"перв\w* лини|у моря|у пляжа|на пляже|свой пляж|собственн\w* пляж|рядом с пляжем|beachfront"),
        _re(r"beachfront|private beach|^beach$|beach access"),
    ),
    Need("pets", "pets", _re(r"собак|кошк|питом|животн|\bpets?\b|\bdogs?\b|\bcats?\b")),
    Need(
        "all_inclusive",
        "rate",
        _re(r"вс[её] включено|all ?inclusive|ультра"),
        meals=frozenset({"all_inclusive"}),
    ),
    Need(
        "half_board",
        "rate",
        _re(r"полупансион|ужин|half ?board"),
        meals=frozenset({"half_board", "full_board", "all_inclusive"}),
    ),
    Need("breakfast", "rate", _re(r"завтрак|breakfast"), meals=BOARD_AND_MORE),
    Need("free_cancel", "rate", _re(r"отмен|refundable|cancel")),
)


def need_of(wish: str) -> Need | None:
    return next((n for n in NEEDS if n.asks.search(wish)), None)


def reads_rooms(wishes: list[str]) -> bool:
    """Whether a wish is answered only by the hotel's own page: a room's amenities, its facilities, its rules."""
    return any((n := need_of(w)) and (n.amenity or n.scope in ("hotel", "pets")) for w in wishes)


def _proves(need: Need, text: str) -> bool:
    return bool(need.proof and need.proof.search(text)) and not (
        need.not_proof and need.not_proof.search(text)
    )


def _on_rate(need: Need, rate: Rate, room: Room | None) -> tuple[Verdict, str | None]:
    """Whether this rate's room or terms have it, and the words of the data that say so."""
    if need.key == "free_cancel":
        return ("yes" if rate.free_cancel_days is not None else "no"), None
    if need.scope == "rate":
        return ("yes" if rate.meal in need.meals else "no"), None
    names = [n for n in (rate.room, room.name if room else None) if n]
    texts = [*names, *(room.views if room else ()), *(room.amenities if room else ())]
    if proof := next((t for t in texts if _proves(need, t)), None):
        return "yes", proof
    if need.view and (shown := [*(room.views if room else ()), *(n for n in names if ANY_VIEW.search(n))]):
        return "no", shown[0]
    if need.amenity and room and len(room.amenities) >= LISTED_AMENITIES:
        return "no", None
    return "unknown", None


def _at_hotel(need: Need, details: Details | None) -> tuple[Verdict, str | None]:
    """The hotel's facilities and rules: a facility named is a yes; one not named is not a no."""
    if details is None:
        return "unknown", None
    if need.scope == "pets":
        if details.pets is None:
            return "unknown", None
        return ("yes", "Pets allowed") if details.pets else ("no", "Pets not allowed")
    texts = [*details.facilities, *(a for room in details.rooms for a in room.amenities)]
    proof = next((t for t in texts if _proves(need, t)), None)
    return ("yes", proof) if proof else ("unknown", None)


def _none_on_sale(need: Need, rates: tuple[Rate, ...]) -> str:
    if need.scope == "rate" and need.meals:
        meals = dict.fromkeys(MEAL_LABELS[r.meal] for r in sorted(rates, key=lambda r: r.night_rub))
        return f"на ваши даты только: {', '.join(meals)}"
    return NONE_ON_SALE


def judge(
    wishes: list[str], rates: tuple[Rate, ...], details: Details | None
) -> tuple[tuple[Evidence, ...], tuple[Rate, ...]]:
    """Evidence for every wish this vocabulary knows, and the rates whose rooms and terms fit the most of them:
    of those, the ones that fit the same wishes as the cheapest, so the room the plan books is the room shown."""
    asked = [(w, n) for w in wishes if (n := need_of(w))]
    if not asked:
        return (), rates
    rooms = {r.id: r for r in details.rooms} if details else {}
    on_rate = [(w, n) for w, n in asked if n.scope in ("room", "rate")]
    said = [{w: _on_rate(n, r, rooms.get(r.room_id or "")) for w, n in on_rate} for r in rates]

    def met(i: int, verdict: Verdict = "yes") -> frozenset[str]:
        return frozenset(w for w, (v, _) in said[i].items() if v == verdict)

    def fit(i: int) -> tuple[int, int]:  # the most wishes met, then the fewest a room is known to lack
        return len(met(i)), -len(met(i, "no"))

    kept = list(range(len(rates)))
    if on_rate and rates:
        best = max(fit(i) for i in kept)
        cheapest = min((i for i in kept if fit(i) == best), key=lambda i: rates[i].night_rub)
        kept = [i for i in kept if met(i) == met(cheapest) and met(i, "no") == met(cheapest, "no")]
    first = min(kept, key=lambda i: rates[i].night_rub) if kept else None
    evidence = []
    for wish, need in asked:
        if need.scope in ("hotel", "pets"):
            verdict, proof = _at_hotel(need, details)
            evidence.append(Evidence(wish, verdict, proof, None if proof else NOT_SAID, LITEAPI))
            continue
        verdicts = [s[wish] for s in said]
        if first is not None and said[first][wish][0] == "yes":
            proof = said[first][wish][1]
            note = "частичный" if proof and PARTIAL.search(proof) else None
            # a room is proved by its own name at least; a meal plan or a refund by the rate itself
            quote = proof or (rates[first].room if need.scope == "room" else None)
            evidence.append(Evidence(wish, "yes", quote, note, LITEAPI))
        elif any(v == "yes" for v, _ in verdicts):
            evidence.append(Evidence(wish, "unknown", None, OTHER_ROOM, LITEAPI))
        elif verdicts and all(v == "no" for v, _ in verdicts):
            evidence.append(Evidence(wish, "no", verdicts[0][1], _none_on_sale(need, rates), LITEAPI))
        else:
            evidence.append(Evidence(wish, "unknown", None, NOT_SAID, LITEAPI))
    return tuple(evidence), tuple(rates[i] for i in kept)
