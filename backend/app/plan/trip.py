"""One assembled trip, in three shapes: what the plan on screen draws, what the model reads to explain it,
and the short summary the next plan is compared with."""

from dataclasses import asdict, dataclass, field
from datetime import date, datetime

from app.catalog.catalog import Place
from app.catalog.search import Snapshot
from app.flights.dictionary import airline_name
from app.money import money
from app.photos import place_photo
from app.plan.checks import Check
from app.plan.guide import Guide
from app.plan.hotels import MEAL_LABELS, Evidence, HotelChoice, HotelPick, Party
from app.plan.itinerary import Day
from app.plan.transfers import Transfer
from app.trip.brief import plural
from app.trip.routes import Leg

MONTHS_OF = (
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
)
SIGHTS_FOR_MODEL = 4
FOOD_FOR_MODEL = 3
DEMO_NOTE = (
    "Hotels are demo data shaped like Ostrovok offers: say so once, briefly. Tickets are real Aviasales prices; "
    "a transfer with a source is the city's airport taxi fare found on the web, scaled to the hotel; one "
    "without is an estimate by distance at the country's prices; ground hops are estimates by distance."
)


def day_text(day: date) -> str:
    return f"{day.day} {MONTHS_OF[day.month - 1]}"


def span_text(start: date, end: date) -> str:
    if start.month == end.month:
        return f"{start.day}–{end.day} {MONTHS_OF[end.month - 1]}"
    return f"{day_text(start)} – {day_text(end)}"


def _local(moment: datetime | None) -> str | None:
    return moment.strftime("%Y-%m-%dT%H:%M") if moment else None


def _hm(moment: datetime | None) -> str | None:
    return moment.strftime("%H:%M") if moment else None


@dataclass(frozen=True)
class Move:
    """A leg with its local times; times are None when the tickets do not follow the plan's dates."""

    leg: Leg
    departs: datetime | None = None
    arrives: datetime | None = None
    price_rub: int | None = None  # a ground hop per person, an estimate

    def view(self) -> dict:
        return {
            **self.leg.view(),
            "departs": _local(self.departs),
            "arrives": _local(self.arrives),
            "ground_rub": self.price_rub,
        }

    def for_model(self) -> dict:
        view = {"from": self.leg.origin, "to": self.leg.destination, "mode": self.leg.mode}
        if self.departs:
            view["when"] = (
                f"{day_text(self.departs.date())}, {_hm(self.departs)} → {_hm(self.arrives) or '?'}"
            )
        ticket = self.leg.ticket
        if ticket:
            stops = "прямой" if ticket.transfers == 0 else f"пересадок: {ticket.transfers}"
            view["flight"] = (
                f"{airline_name(ticket.airline)} {ticket.airline} {ticket.flight_number}, {stops}"
            )
            view["price_per_person"] = money(ticket.price)
        elif self.price_rub:
            view["estimate_per_person"] = money(self.price_rub)
            view["hours"] = self.leg.hours
        return view


def choice_view(c: HotelChoice) -> dict:
    h = c.hotel
    return {
        "id": h.id,
        "name": h.name,
        "stars": h.stars,
        "rating": h.rating,
        "reviews": h.reviews,
        "area": h.area,
        "beach_m": h.beach_m,
        "meal": c.rate.meal,
        "meal_label": MEAL_LABELS[c.rate.meal],
        "free_cancel_days": c.rate.free_cancel_days,
        "pay_at_hotel": c.rate.pay_at_hotel,
        "rooms": c.rooms,
        "nights": c.nights,
        "night_rub": c.night_rub,
        "total_rub": c.total_rub,
        "check_in": h.check_in.strftime("%H:%M"),
        "check_out": h.check_out.strftime("%H:%M"),
        "reasons": c.reasons,
        "misses": c.misses,
        # a real hotel: its name, place, stars and photo are real, the price is our estimate until booking
        "demo": not h.real,
        "real": h.real,
        "stars_known": h.stars_known,
        "photo": h.photo,
        "source_url": h.source_url,
        "price_estimate": c.rate.estimate or not h.real,
        "terms_known": c.rate.terms_known,
        "evidence": [asdict(e) for e in h.evidence],
    }


VERDICT_FOR_MODEL = {"yes": "подтверждено", "no": "нет", "unknown": "не подтверждено"}


def wish_for_model(e: Evidence) -> str:
    """«с видом на море: подтверждено (номера с балконом), otzovik.com»"""
    note = f" ({e.note})" if e.note else ""
    return f"{e.wish}: {VERDICT_FOR_MODEL[e.verdict]}{note}" + (f", {e.source}" if e.source else "")


def _choice_for_model(c: HotelChoice) -> dict:
    h = c.hotel
    return {
        "id": h.id,
        "name": h.name,
        "stars": h.stars,
        "rating": h.rating,
        "area": h.area,
        # a meal plan we only estimated is not something to promise
        "meal": MEAL_LABELS[c.rate.meal] if c.rate.terms_known else "питание уточним при бронировании",
        "total": money(c.total_rub),
        "real_hotel": h.real,  # real name and place; the price is an estimate, terms are confirmed at booking
        "price_is_estimate": c.rate.estimate or not h.real,
        "why": c.reasons,
        "misses": c.misses,
        "wishes": [wish_for_model(e) for e in h.evidence],
    }


@dataclass(frozen=True)
class StopPlan:
    snapshot: Snapshot
    check_in: date
    check_out: date
    pick: HotelPick
    guide: Guide
    transfer_in: Transfer | None = None
    transfer_out: Transfer | None = None

    @property
    def place(self) -> Place:
        return self.snapshot.place

    @property
    def nights(self) -> int:
        return (self.check_out - self.check_in).days

    @property
    def transfers_rub(self) -> int:
        return sum(t.price_rub for t in (self.transfer_in, self.transfer_out) if t)

    def view(self) -> dict:
        guide = self.guide
        return {
            "place_id": self.place.id,
            "name": self.place.name,
            "country": self.place.country.name,
            "country_code": self.place.country.code,
            "kinds": list(self.place.kinds),
            "check_in": self.check_in.isoformat(),
            "check_out": self.check_out.isoformat(),
            "nights": self.nights,
            "photo": place_photo(self.place.id),
            "source_url": guide.source_url,
            "hotel": choice_view(self.pick.best),
            "alternatives": [choice_view(a) for a in self.pick.alternatives],
            "excluded": [{"name": h.name, "stars": h.stars, "reason": why} for h, why in self.pick.excluded],
            "transfer_in": self.transfer_in.view() if self.transfer_in else None,
            "transfer_out": self.transfer_out.view() if self.transfer_out else None,
            "food_intro": guide.food_intro,
            "dishes": [{"name": d.name, "note": d.note} for d in guide.dishes],
        }


FARE_DRIFT = 0.1  # cached fares are a few days old: the same ticket may cost this much more at booking
RIDE_SPREAD = 0.25  # a taxi or a bus estimated by distance
HOTEL_SPREAD = (0.85, 1.2)  # an estimated room price, low and high


@dataclass(frozen=True)
class Costs:
    flights: int
    hotels: int
    transfers: int
    ground: int
    guests: int
    flights_complete: bool  # every flight leg has a ticket, so the total is the whole cost
    budget: int | None = None
    # The cheapest and the dearest the same trip may come to. Tickets are real cached prices, hotels and
    # rides are estimates: they get a spread, and the lower end takes the cheapest hotel offered instead.
    hotels_low: int | None = None
    hotels_high: int | None = None
    hotels_estimate: bool = True

    @property
    def low(self) -> int:
        hotels = self.hotels_low if self.hotels_low is not None else self.hotels
        return round(self.flights + hotels + (self.transfers + self.ground) * (1 - RIDE_SPREAD))

    @property
    def high(self) -> int:
        hotels = self.hotels_high if self.hotels_high is not None else self.hotels
        return round(
            self.flights * (1 + FARE_DRIFT) + hotels + (self.transfers + self.ground) * (1 + RIDE_SPREAD)
        )

    @property
    def total(self) -> int:
        return self.flights + self.hotels + self.transfers + self.ground

    @property
    def per_person(self) -> int:
        return round(self.total / self.guests)

    @property
    def over_by(self) -> int | None:
        return self.total - self.budget if self.budget and self.total > self.budget else None

    def view(self) -> dict:
        return {
            "flights": self.flights,
            "hotels": self.hotels,
            "transfers": self.transfers,
            "ground": self.ground,
            "total": self.total,
            "per_person": self.per_person,
            "guests": self.guests,
            "flights_complete": self.flights_complete,
            "low": self.low,
            "high": self.high,
            "hotels_estimate": self.hotels_estimate,
            "budget": self.budget,
            "over_by": self.over_by,
        }

    def for_model(self) -> dict:
        parts = {
            "total": money(self.total),
            "per_person": money(self.per_person),
            "flights": money(self.flights) if self.flights else None,
            "hotels": money(self.hotels),
            "transfers": money(self.transfers) if self.transfers else None,
            "ground_estimate": money(self.ground) if self.ground else None,
        }
        if not self.flights_complete:
            parts["note"] = "some flights have no tickets yet, so the total leaves them out"
        if self.budget:
            parts["budget"] = money(self.budget)
            parts["over_budget_by"] = money(self.over_by) if self.over_by else None
        return parts


@dataclass(frozen=True)
class TripPlan:
    id: str
    name: str
    party: Party
    stops: list[StopPlan]
    moves: list[Move]
    checks: list[Check]
    days: list[Day]
    costs: Costs
    dates_fixed: bool  # the tickets follow the plan's dates; otherwise dates are ours and times unknown
    unmet: list[str] = field(default_factory=list)
    wishes_not_checked: list[str] = field(default_factory=list)
    changes: list[str] = field(default_factory=list)

    @property
    def start(self) -> date:
        return self.stops[0].check_in

    @property
    def end(self) -> date:
        return self.stops[-1].check_out

    @property
    def nights(self) -> int:
        return (self.end - self.start).days

    def _party_text(self) -> str:
        p = self.party
        text = f"{p.adults} {plural(p.adults, ('взрослый', 'взрослых', 'взрослых'))}"
        if p.children_ages:
            ages = ", ".join(str(a) for a in p.children_ages)
            text += f" и {len(p.children_ages)} {plural(len(p.children_ages), ('ребёнок', 'ребёнка', 'детей'))} ({ages})"
        return text

    def view(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "dates": {"from": self.start.isoformat(), "to": self.end.isoformat(), "nights": self.nights},
            "dates_fixed": self.dates_fixed,
            "party": {"adults": self.party.adults, "children_ages": list(self.party.children_ages)},
            "stops": [s.view() for s in self.stops],
            "legs": [m.view() for m in self.moves],
            "checks": [c.view() for c in self.checks],
            "days": [d.view() for d in self.days],
            "costs": self.costs.view(),
            "unmet": self.unmet,
            "changes": self.changes,
        }

    def for_model(self) -> dict:
        planned = [i for d in self.days for i in d.items if i.spot]
        stops = []
        for s in self.stops:
            stops.append(
                {
                    "name": s.place.name,
                    "nights": s.nights,
                    "hotel": _choice_for_model(s.pick.best),
                    "alternatives": [_choice_for_model(a) for a in s.pick.alternatives],
                    "ruled_out": [f"{h.name}: {why}" for h, why in s.pick.excluded][:3],
                    "transfer": s.transfer_in.view() if s.transfer_in else None,
                    "sights": [
                        i.spot.name
                        for i in planned
                        if i.kind in ("sight", "trip") and i.spot in s.guide.sights
                    ][:SIGHTS_FOR_MODEL],
                    "food": [i.spot.name for i in planned if i.kind == "food" and i.spot in s.guide.food][
                        :FOOD_FOR_MODEL
                    ],
                    "dishes": [d.name for d in s.guide.dishes][:FOOD_FOR_MODEL],
                }
            )
        return {
            "id": self.id,
            "name": self.name,
            "dates": f"{span_text(self.start, self.end)}, {self.nights} {plural(self.nights, ('ночь', 'ночи', 'ночей'))}",
            "dates_fixed": self.dates_fixed,
            "party": self._party_text(),
            "legs": [m.for_model() for m in self.moves],
            "stops": stops,
            "checks": [f"{c.level}: {c.title}. {c.text}" for c in self.checks],
            "costs": self.costs.for_model(),
            "unmet": self.unmet,
            "wishes_not_checked": self.wishes_not_checked,
            "changes": self.changes,
            "days": [f"{day_text(d.date)}: {d.title}" for d in self.days],
            "note": DEMO_NOTE,
        }

    def summary(self) -> dict:
        """Kept in the brief, so the next plan can say what changed and the model can name other hotels."""
        return {
            "id": self.id,
            "name": self.name,
            "check_in": self.start.isoformat(),
            "check_out": self.end.isoformat(),
            "guests": self.party.guests,
            "total_rub": self.costs.total,
            "hotels": {
                s.place.id: {"id": s.pick.best.hotel.id, "name": s.pick.best.hotel.name} for s in self.stops
            },
            "alternatives": [
                {"place": s.place.name, "id": a.hotel.id, "name": a.hotel.name, "stars": a.hotel.stars}
                for s in self.stops
                for a in s.pick.alternatives
            ],
        }
