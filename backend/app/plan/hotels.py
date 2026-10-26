"""Demo hotels: generated per place from a seed, priced by a calibrated formula, never shown as real.

There is no open source of real hotel prices and rooms for our places (docs/07, docs/08), so each place
gets the same handful of hotels every time, shaped like an Ostrovok offer: hotel → rate with a meal plan,
a cancellation rule and a payment type. The UI labels every one of them as a demo.
"""

import hashlib
import math
import random
from dataclasses import dataclass, field
from datetime import time
from typing import Literal

from app.catalog.catalog import Place

Meal = Literal["room_only", "breakfast", "half_board", "all_inclusive"]
MEAL_LABELS: dict[Meal, str] = {
    "room_only": "без питания",
    "breakfast": "завтраки",
    "half_board": "завтраки и ужины",
    "all_inclusive": "всё включено",
}
MEAL_FACTOR: dict[Meal, float] = {"room_only": 1.0, "breakfast": 1.1, "half_board": 1.3, "all_inclusive": 1.6}
# A room for two, 3 stars, average season, by the catalogue price level. Anchored on RUTI's Russian averages
# (8-9 thousand a night) and Türkiye, Dubai and Thailand ADR figures (docs/07-data-sources.md).
NIGHT_BASE_RUB = {1: 4000, 2: 6500, 3: 11000}
STAR_FACTOR = {3: 1.0, 4: 1.5, 5: 2.4}
TARGET_STARS = {0: 4, 1: 3, 2: 4, 3: 5}
# Resorts where all inclusive is the usual way to sell a beach holiday.
ALL_INCLUSIVE_COUNTRIES = {"TR", "EG", "TN", "CU", "MV", "MU"}
EXTRA_GUEST_FACTOR = 0.2
ROOM_SIZE = 3  # two adults and a child sleep in one room; four people need two
HOTELS_PER_PLACE = 6

NAMES = (
    "Лазурная бухта",
    "Морской бриз",
    "Апельсиновый сад",
    "Старая гавань",
    "Белые камни",
    "Тихий двор",
    "Дом у маяка",
    "Солнечная терраса",
    "Северный ветер",
    "Горный приют",
    "Зелёная долина",
    "Каменный мост",
    "Песчаная коса",
    "Синие ставни",
)
AREAS = {
    "sea": ("на первой линии", "у моря", "в центре"),
    "city": ("в историческом центре", "в центре", "в спокойном районе"),
    "ski": ("у подъёмника", "в посёлке", "с видом на горы"),
    "mountains": ("с видом на горы", "в посёлке", "в центре"),
    "nature": ("в посёлке", "у воды", "в центре"),
}
WISH_WORDS = {
    "all_inclusive": ("всё включено", "все включено", "all inclusive", "ультра"),
    "pets": ("собак", "кошк", "питом", "животн", "dog", "pet"),
    "beach": ("первая линия", "первой линии", "у моря", "у пляжа", "рядом с пляжем", "first line"),
    "spa": ("спа", "spa"),
    "quiet": ("тих", "спокойн", "quiet"),
}


@dataclass(frozen=True)
class Rate:
    meal: Meal
    night_rub: int  # a room for two, one night
    free_cancel_days: int | None  # free cancellation until this many days before arrival; None: no refund
    pay_at_hotel: bool
    terms_known: bool = True  # False for an estimate: the meal, refund and payment rules are not known yet
    estimate: bool = False  # the price is our estimate, not a provider's offer


@dataclass(frozen=True)
class Hotel:
    id: str
    place_id: str
    name: str
    stars: int
    rating: float | None
    reviews: int | None
    area: str
    lat: float
    lon: float
    beach_m: int | None
    kids_club: bool
    family_rooms: bool
    adults_only: bool
    pets: bool
    pool: bool
    spa: bool
    reception_24h: bool
    check_in: time
    check_out: time
    early_check_in_rub: int
    late_check_out_rub: int
    rates: tuple[Rate, ...]
    # A real hotel from the directory (app/hotels): its name, place, stars and photo are real; its features
    # above are unknown, so nothing is claimed from them. A demo hotel (real=False) is invented whole.
    real: bool = False
    stars_known: bool = True
    photo: dict | None = field(default=None, hash=False, compare=False)  # not part of who the hotel is
    source_url: str | None = None
    centre_m: int | None = None


@dataclass(frozen=True)
class Party:
    adults: int = 2
    children_ages: tuple[int, ...] = ()

    @property
    def guests(self) -> int:
        return self.adults + len(self.children_ages)

    @property
    def rooms(self) -> int:
        return math.ceil(self.guests / ROOM_SIZE)

    @property
    def small_kids(self) -> bool:
        return any(age < 6 for age in self.children_ages)


@dataclass(frozen=True)
class Wishes:
    all_inclusive: bool = False
    pets: bool = False
    beach: bool = False
    spa: bool = False
    quiet: bool = False


@dataclass(frozen=True)
class HotelChoice:
    hotel: Hotel
    rate: Rate
    rooms: int
    nights: int
    night_rub: int  # all rooms for the party, one night
    reasons: list[str] = field(default_factory=list)
    misses: list[str] = field(default_factory=list)

    @property
    def total_rub(self) -> int:
        return self.night_rub * self.nights


@dataclass(frozen=True)
class HotelPick:
    best: HotelChoice
    alternatives: list[HotelChoice]
    excluded: list[tuple[Hotel, str]]
    unmet: list[str]


def hundreds(value: float) -> int:
    """A price as people say it: 15 437.5 → 15 400."""
    return round(value / 100) * 100


def party_night(rate: Rate, party: Party) -> int:
    """One night for the whole party: enough rooms, and a share more for every guest beyond two a room."""
    extra = 1 + EXTRA_GUEST_FACTOR * max(0, party.guests - 2 * party.rooms)
    return hundreds(rate.night_rub * party.rooms * extra)


def cheapest_rate(hotel: Hotel) -> Rate:
    return _rate(hotel, False)


def wishes_from(words: list[str] | None) -> Wishes:
    text = " ".join(words or []).casefold()
    return Wishes(**{wish: any(w in text for w in keys) for wish, keys in WISH_WORDS.items()})


def _rng(*parts: object) -> random.Random:
    seed = hashlib.sha256("|".join(map(str, parts)).encode()).digest()
    return random.Random(int.from_bytes(seed[:8], "big"))


def season_factor(place: Place, month: int | None) -> float:
    if month is None:
        return 1.0
    if "ski" in place.kinds:
        return 1.4 if month in (12, 1, 2, 3) else 0.8
    if "sea" in place.kinds:
        if abs(place.lat) <= 23:  # the tropics: the dry winter is the high season
            return 1.3 if month in (12, 1, 2, 3) else 1.0 if month in (4, 11) else 0.85
        return 1.35 if month in (6, 7, 8, 9) else 1.0 if month in (5, 10) else 0.8
    return 1.15 if month == 12 else 1.1 if month in (6, 7, 8) else 1.0


def _meals(place: Place, stars: int) -> list[Meal]:
    resort = bool({"sea", "ski", "mountains"} & set(place.kinds))
    meals: list[Meal] = ["breakfast"]
    if stars <= 4:
        meals.insert(0, "room_only")
    if resort:
        meals.append("half_board")
    if "sea" in place.kinds and place.country.code in ALL_INCLUSIVE_COUNTRIES and stars >= 4:
        meals.append("all_inclusive")
    return meals


def _hotel(place: Place, index: int, name: str, stars: int, month: int | None, adults_only: bool) -> Hotel:
    rng = _rng(place.id, index)
    kind = next((k for k in ("sea", "ski", "city", "mountains", "nature") if k in place.kinds), "city")
    area = rng.choice(AREAS[kind])
    beach_m = None
    if kind == "sea":
        beach_m = (
            rng.randint(30, 120)
            if area == "на первой линии"
            else rng.randint(150, 450)
            if area == "у моря"
            else rng.randint(600, 1500)
        )
    spread = 0.04 if area.startswith("в центре") or area == "в историческом центре" else 0.09
    factor = rng.uniform(0.85, 1.2)
    base = NIGHT_BASE_RUB[place.price_level] * STAR_FACTOR[stars] * season_factor(place, month) * factor
    cancel = rng.choice((None, 1, 3, 7))
    pay_at_hotel = rng.random() < 0.5
    rates = tuple(
        Rate(meal, hundreds(base * MEAL_FACTOR[meal]), cancel, pay_at_hotel) for meal in _meals(place, stars)
    )
    family = not adults_only and (stars >= 4 or rng.random() < 0.5)
    return Hotel(
        id=f"{place.id}-h{index}",
        place_id=place.id,
        name=name,
        stars=stars,
        rating=round(rng.uniform(7.6, 9.0) + (0.4 if stars == 5 else 0), 1),
        reviews=rng.randint(120, 3400),
        area=area,
        lat=round(place.lat + rng.uniform(-spread, spread), 5),
        lon=round(place.lon + rng.uniform(-spread, spread), 5),
        beach_m=beach_m,
        kids_club=not adults_only and stars >= 4 and kind == "sea" and rng.random() < 0.7,
        family_rooms=family,
        adults_only=adults_only,
        pets=not adults_only and rng.random() < 0.3,
        pool=stars >= 4 or kind == "sea",
        spa=stars == 5 or rng.random() < 0.25,
        reception_24h=stars >= 4 or rng.random() < 0.6,
        check_in=time(14),
        check_out=time(12),
        early_check_in_rub=hundreds(base * 0.5),
        late_check_out_rub=hundreds(base * 0.5),
        rates=rates,
    )


def hotels_for(place: Place, month: int | None) -> list[Hotel]:
    """The place's demo hotels: the same names, stars and features every time, prices for the month."""
    rng = _rng(place.id, "names")
    names = rng.sample(NAMES, HOTELS_PER_PLACE)
    stars = (3, 3, 4, 4, 5, 5)
    adult = rng.choice((3, 5))  # one 4 or 5 star hotel is adults only
    return [
        _hotel(place, i, names[i], stars[i], month, adults_only=i == adult) for i in range(HOTELS_PER_PLACE)
    ]


def _rate(hotel: Hotel, all_inclusive: bool) -> Rate:
    by_meal = {r.meal: r for r in hotel.rates}
    if all_inclusive and "all_inclusive" in by_meal:
        return by_meal["all_inclusive"]
    return by_meal.get("breakfast") or hotel.rates[0]


def _explain(
    hotel: Hotel, rate: Rate, party: Party, wishes: Wishes, sea: bool
) -> tuple[list[str], list[str]]:
    reasons, misses = [], []
    if hotel.real:  # only what the directory knows: where it is and its stars
        if hotel.centre_m is not None and hotel.centre_m <= 1500:
            reasons.append("в центре")
        if hotel.stars_known:
            reasons.append(f"{hotel.stars}★")
        return reasons, misses
    if party.children_ages:
        (reasons if hotel.kids_club else misses).append(
            "детский клуб" if hotel.kids_club else "нет детского клуба"
        )
    if party.guests >= 3 and hotel.family_rooms:
        reasons.append("семейный номер")
    if sea and hotel.beach_m is not None:
        if hotel.beach_m <= 120:
            reasons.append(f"первая линия, до пляжа {hotel.beach_m} м")
        elif hotel.beach_m > 600:
            misses.append(f"до пляжа {hotel.beach_m} м")
    if rate.meal == "all_inclusive":
        reasons.append("всё включено")
    if rate.free_cancel_days is not None:
        reasons.append("бесплатная отмена")
    else:
        misses.append("без бесплатной отмены")
    if hotel.rating >= 9:
        reasons.append(f"оценка гостей {hotel.rating:.1f}".replace(".", ","))
    if wishes.pets and hotel.pets:
        reasons.append("можно с животными")
    if wishes.spa and hotel.spa:
        reasons.append("есть спа")
    return reasons, misses


def _score(hotel: Hotel, rate: Rate, party: Party, wishes: Wishes, target: int, cheapest: int) -> float:
    rating = (hotel.rating - 8) * 0.5 if hotel.rating else 0.0
    score = -abs(hotel.stars - target) + rating - 0.3 * rate.night_rub / cheapest
    if hotel.real:  # known stars beat a guess; close to the centre is what we can tell about the place
        score -= 0.5 * (not hotel.stars_known)
        score += 0.4 * (hotel.centre_m is not None and hotel.centre_m <= 2000)
    if party.children_ages:
        score += 1.5 * hotel.kids_club + 0.8 * (hotel.family_rooms and party.guests >= 3)
        score += 0.6 * (hotel.beach_m is not None and hotel.beach_m <= 200)
    if wishes.beach:
        score += 1.0 if hotel.beach_m is not None and hotel.beach_m <= 150 else -0.5
    if wishes.all_inclusive:
        score += 2.0 * (rate.meal == "all_inclusive")
    score += 1.0 * (wishes.spa and hotel.spa) + 0.7 * (wishes.quiet and hotel.area == "в спокойном районе")
    score += 0.3 * (rate.free_cancel_days is not None)
    return score


def choose_hotel(
    hotels: list[Hotel],
    party: Party,
    wishes: Wishes,
    level: int | None,
    nights: int,
    prefer: str | None = None,
) -> HotelPick:
    """The hotel that fits this party best, a cheaper and a more comfortable one, and what was ruled out."""
    place_ai = any(r.meal == "all_inclusive" for h in hotels for r in h.rates)
    # families in an all-inclusive resort get it by default: that is how these trips are sold there
    all_inclusive = wishes.all_inclusive or (place_ai and bool(party.children_ages))
    excluded = [
        (h, "только для взрослых, а с вами ребёнок") for h in hotels if h.adults_only and party.children_ages
    ]
    unmet = []
    if all(h.real for h in hotels):
        return _choose_real(hotels, party, wishes, level, nights, prefer)
    if wishes.pets:
        if any(h.pets for h in hotels):
            excluded += [
                (h, "без животных")
                for h in hotels
                if not h.pets and not (h.adults_only and party.children_ages)
            ]
        else:
            unmet.append("Отелей, куда можно с животными, здесь не нашлось")
    if wishes.all_inclusive and not place_ai:
        unmet.append("Отелей «всё включено» здесь нет, поэтому беру с завтраками")
    if wishes.beach and not any(h.beach_m is not None and h.beach_m <= 150 for h in hotels):
        unmet.append("Отелей на первой линии здесь нет, беру ближайший к пляжу")
    ruled_out = {h.id for h, _ in excluded}
    allowed = [h for h in hotels if h.id not in ruled_out] or hotels
    sea = any(h.beach_m is not None for h in hotels)
    target = TARGET_STARS[level or 0]
    rates = {h.id: _rate(h, all_inclusive) for h in allowed}
    cheapest = min(r.night_rub for r in rates.values())

    def choice(h: Hotel) -> HotelChoice:
        rate = rates[h.id]
        night = party_night(rate, party)
        reasons, misses = _explain(h, rate, party, wishes, sea)
        return HotelChoice(h, rate, party.rooms, nights, night, reasons, misses)

    ranked = sorted(allowed, key=lambda h: -_score(h, rates[h.id], party, wishes, target, cheapest))
    best = next((h for h in allowed if h.id == prefer), ranked[0])
    rest = [h for h in ranked if h.id != best.id]
    cheaper = min(
        (h for h in rest if rates[h.id].night_rub < rates[best.id].night_rub),
        key=lambda h: rates[h.id].night_rub,
        default=None,
    )
    nicer = next(
        (h for h in rest if h.stars > best.stars or (h.rating or 0) > (best.rating or 0) + 0.3), None
    )
    alternatives = [choice(h) for h in dict.fromkeys(x for x in (cheaper, nicer) if x)]
    return HotelPick(choice(best), alternatives, excluded, unmet)


UNKNOWN_FOR_REAL = {
    "pets": "Можно ли с животными, по этим отелям не знаю: уточним при бронировании",
    "all_inclusive": "Есть ли «всё включено», уточним при бронировании",
    "beach": "Как далеко от пляжа, уточним по каждому отелю",
    "spa": "Есть ли спа, уточним при бронировании",
}


def _choose_real(
    hotels: list[Hotel], party: Party, wishes: Wishes, level: int | None, nights: int, prefer: str | None
) -> HotelPick:
    """Real hotels: chosen by stars, the centre and the estimated price; every wish we cannot check is said."""
    unmet = [text for wish, text in UNKNOWN_FOR_REAL.items() if getattr(wishes, wish)]
    target = TARGET_STARS[level or 0]
    rates = {h.id: _rate(h, False) for h in hotels}
    cheapest = min(r.night_rub for r in rates.values())

    def choice(h: Hotel) -> HotelChoice:
        rate = rates[h.id]
        night = party_night(rate, party)
        reasons, misses = _explain(h, rate, party, wishes, False)
        return HotelChoice(h, rate, party.rooms, nights, night, reasons, misses)

    ranked = sorted(hotels, key=lambda h: -_score(h, rates[h.id], party, wishes, target, cheapest))
    best = next((h for h in hotels if h.id == prefer), ranked[0])
    rest = [h for h in ranked if h.id != best.id]
    cheaper = min(
        (h for h in rest if rates[h.id].night_rub < rates[best.id].night_rub),
        key=lambda h: rates[h.id].night_rub,
        default=None,
    )
    nicer = next((h for h in rest if h.stars_known and h.stars > best.stars), None)
    # without stars to compare, the runner-up stands in for «nicer», so there is always a choice
    runner_up = next((h for h in rest if h not in (cheaper, nicer)), None)
    alternatives = [choice(h) for h in dict.fromkeys(x for x in (cheaper, nicer or runner_up) if x)]
    return HotelPick(choice(best), alternatives, [], unmet)
