"""The tools that turn a pick into a trip: build_trip assembles it in code, show_trip puts it on screen
with the agent's own words. Built per chat around the same TripState as the trip tools."""

from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, date, datetime
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.catalog.catalog import load_catalog
from app.destinations import snapshots_by_id
from app.flights import Flights, NoFlights, city, current_origin
from app.hotels import HotelSource
from app.hotels.evidence import hotel_wishes
from app.maps import google_maps_url
from app.money import current_currency, money
from app.photos import ensure_photos
from app.plan.assemble import _start, assemble, party_of
from app.plan.hotels import MEAL_LABELS, Hotel, cheapest_rate, hotels_for, party_night
from app.plan.trip import TripPlan, wish_for_model
from app.tools import Tool, ToolReply
from app.trip.brief import cards_first, chips, night_range, price_level
from app.trip.routes import DEFAULT_NIGHTS
from app.trip.tools import TripState

MAX_STOPS = 3
CENTRE_M = 2000
# tickets, then hotels checked against the wishes on their sites and in reviews (evidence.py waits up to 25 s)
HOTEL_TOOL_TIMEOUT_S = 60.0


def _central(h: Hotel) -> bool:
    if h.centre_m is not None:
        return h.centre_m <= CENTRE_M
    return h.area in ("в центре", "в историческом центре")


def _hotel_card(h: Hotel, rate, night: int, nights: int, current: bool) -> dict:
    """One hotel as the «more hotels» card draws it; real ones carry their photo and source."""
    return {
        "id": h.id,
        "name": h.name,
        "stars": h.stars,
        "stars_known": h.stars_known,
        "area": h.area,
        "photo": h.photo,
        "source_url": h.source_url,
        # an invented demo hotel has no place on any map
        "maps_url": google_maps_url(h.name, h.lat, h.lon) if h.real else None,
        "real": h.real,
        "meal_label": MEAL_LABELS[rate.meal],
        "night_rub": night,
        "total_rub": night * nights,
        "total": money(night * nights),
        "price_estimate": rate.estimate or not h.real,
        "terms_known": rate.terms_known,
        "current": current,
        "evidence": [asdict(e) for e in h.evidence],
    }


BUILD_DESCRIPTION = (
    "Assemble the whole trip for what the user picked: tickets on dates that follow the nights, a hotel for this "
    "party with reasons, misses and alternatives, transfers, connection checks (landing vs check-in, check-out vs "
    "the flight home), a day-by-day plan with real sights and local food, and the bill against the budget. "
    "Pass `id`: a place id or a route id ('tbilisi+yerevan') from shown_before or current_plan. To change the "
    "hotel pass `hotels`: ids from the plan's alternatives, or the hotel's name as the user wrote it after "
    "search_hotels («Хочу отель «Ногай»»). Always follow with show_trip."
)
HOTELS_DESCRIPTION = (
    "More hotels in one place of the trip, for its dates and party: real hotels with their stars, photo and "
    "distance from the centre, and the price for the whole stay (an estimate, terms confirmed at booking). "
    "Use it when the user wants other hotels, a cheaper or a central one, or more stars. The list is shown as "
    "cards; the user picks one, then call build_trip with `hotels` set to that hotel's name."
)
SHOW_DESCRIPTION = (
    "Show the plan from build_trip on screen, with a checkout button. `intro` is what you say as the travel "
    "agent who put it together. Ends your turn."
)


class HotelSearchArgs(BaseModel):
    place: str = Field(max_length=80, description="Place id or name in the trip: 'kazan' or 'Казань'.")
    max_night: int | None = Field(
        None, gt=0, description="Most per night for the whole party, in the user's currency."
    )
    min_stars: int | None = Field(None, ge=1, le=5)
    near_centre: bool = Field(False, description="Only hotels within 2 km of the centre.")
    sort: Literal["price", "stars", "centre"] = "price"
    limit: int = Field(6, ge=1, le=10)


class BuildArgs(BaseModel):
    id: str = Field(max_length=120, description="A place id or a route id like 'tbilisi+yerevan'.")
    hotels: list[str] | None = Field(
        None,
        max_length=MAX_STOPS,
        description="Hotel ids the user asked for, one per city; omit to let the code pick.",
    )


class ShowTripArgs(BaseModel):
    intro: str = Field(
        max_length=900,
        description="3-5 warm sentences in the first person, no lists: the dates and flight, why this hotel suits "
        "them, the one thing to know from the checks, and what you could not find with what you offer instead.",
    )


def _build_preview(result: dict) -> str:
    if "error" in result:
        return result["error"]
    return f"{result['name']}: {result['dates']}, всего {result['costs']['total']}"


def _hotel_notes(plan: TripPlan, asked: dict[str, str]) -> list[str]:
    """A hotel the user asked for that the code could not keep, said to the model so it can explain."""
    notes = []
    for stop in plan.stops:
        wanted = asked.get(stop.place.id)
        if wanted and stop.pick.best.hotel.id != wanted:
            why = next((r for h, r in stop.pick.excluded if h.id == wanted), "no such hotel id")
            notes.append(f"{wanted} was not kept: {why}")
    return notes


def plan_tools(
    state: TripState,
    sessionmaker: async_sessionmaker[AsyncSession],
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
    flights: Flights | None = None,
    hotels: HotelSource | None = None,
) -> list[Tool]:
    catalog = load_catalog()
    flights = flights or NoFlights()
    hotels = hotels or HotelSource()
    built: list[TripPlan] = []  # this turn's plan, for show_trip

    async def build_trip(args: BuildArgs) -> dict:
        if refusal := cards_first(state.brief):
            return refusal
        ids = [part.strip() for part in args.id.split("+") if part.strip()]
        places = [catalog.find(i) for i in ids]
        if not 0 < len(places) <= MAX_STOPS or None in places or len({p.id for p in places}) != len(places):
            return {"error": f"Unknown id {args.id!r}: pass a place id or a route id from shown_before."}
        async with sessionmaker() as db:
            snapshots = await snapshots_by_id(db, catalog, now(), [p.id for p in places])
            await ensure_photos(db, places)
        asked = {}
        for wanted in args.hotels or []:
            found = await _hotel_id(wanted, places)
            if found:
                asked[found.rsplit("-h", 1)[0]] = found
        plan = await assemble(
            [snapshots[p.id] for p in places],
            state.brief,
            flights,
            city(current_origin.get()),
            now().date(),
            prefer=asked,
            previous=state.brief.plan,
            hotels=hotels,
        )
        built[:] = [plan]
        result = plan.for_model()
        if notes := _hotel_notes(plan, asked):
            result["hotel_notes"] = notes
        return result

    def _stay(place_id: str) -> tuple[date, int]:
        """The dates the hotels are priced for: the plan's own, else what the brief says."""
        plan = state.brief.plan or {}
        start = (
            date.fromisoformat(plan["check_in"])
            if plan.get("check_in")
            else _start(state.brief, now().date())
        )
        return start, night_range(state.brief)[1] or DEFAULT_NIGHTS

    async def _hotel_id(wanted: str, places) -> str | None:
        """A hotel id as given, or the hotel the user named: «Ногай», «отель Ногай»."""
        ids = {p.id for p in places}
        if "-h" in wanted and wanted.rsplit("-h", 1)[0] in ids:
            return wanted
        needle = wanted.casefold().replace("отель", "").strip(' «»"')
        for place in places:
            start, _ = _stay(place.id)
            names = [(h.id, h.name) for h in await hotels.listing(place)] + [
                (h.id, h.name) for h in hotels_for(place, start.month)
            ]
            match = next((hid for hid, name in names if name.casefold() == needle), None) or next(
                (hid for hid, name in names if needle and needle in name.casefold()), None
            )
            if match:
                return match
        return None

    async def search_hotels(args: HotelSearchArgs) -> dict | ToolReply:
        if refusal := cards_first(state.brief):
            return refusal
        place = catalog.find(args.place)
        if place is None:
            return {"error": f"Unknown place {args.place!r}: pass a place id from the trip."}
        party = party_of(state.brief)
        check_in, nights = _stay(place.id)
        found = await hotels.hotels(place, check_in, nights, party)
        current = ((state.brief.plan or {}).get("hotels") or {}).get(place.id, {}).get("id")
        wishes = hotel_wishes(state.brief.wishes)
        found = await hotels.checked(place, found, wishes, party, price_level(state.brief), current)
        said_no = {h.id for h in found if any(e.verdict == "no" for e in h.evidence)}
        priced = [(h, cheapest_rate(h)) for h in found if h.id not in said_no]
        limit = current_currency.get().to_rub(args.max_night) if args.max_night else None
        priced = [
            (h, r)
            for h, r in priced
            if (limit is None or party_night(r, party) <= limit)
            and (args.min_stars is None or (h.stars_known and h.stars >= args.min_stars))
            and (not args.near_centre or _central(h))
        ]
        order = {
            "price": lambda x: party_night(x[1], party),
            "stars": lambda x: (-(x[0].stars if x[0].stars_known else 0), party_night(x[1], party)),
            "centre": lambda x: (
                x[0].centre_m if x[0].centre_m is not None else (0 if _central(x[0]) else 9999)
            ),
        }[args.sort]
        shown = sorted(priced, key=order)
        # the wishes a source confirms come first, in the asked order within the same count
        shown = sorted(shown, key=lambda x: -sum(e.verdict == "yes" for e in x[0].evidence))[: args.limit]
        cards = [_hotel_card(h, r, party_night(r, party), nights, h.id == current) for h, r in shown]
        result = {
            "place": place.name,
            "check_in": check_in.isoformat(),
            "nights": nights,
            "hotels": [
                {k: c[k] for k in ("name", "stars", "area", "total", "current")}
                | {"price_is_estimate": c["price_estimate"]}
                | ({"wishes": [wish_for_model(e) for e in h.evidence]} if h.evidence else {})
                for c, (h, _) in zip(cards, shown, strict=True)
            ],
            "note": "The hotels are on screen as cards. When the user picks one, call build_trip with `hotels` "
            "set to its name. Prices are estimates for real hotels: say so once.",
        }
        if said_no:
            result["ruled_out"] = [
                f"{h.name}: {wish_for_model(e)}"
                for h in found
                if h.id in said_no
                for e in h.evidence
                if e.verdict == "no"
            ][:3]
        if not cards:
            return {**result, "note": "No hotel fits these filters: say which filter to relax."}
        event = {
            "type": "hotel_options",
            "place": place.name,
            "check_in": check_in.isoformat(),
            "nights": nights,
            "guests": party.guests,
            "hotels": cards,
            "currency": current_currency.get().view(),
        }
        return ToolReply(result=result, event=event)

    async def show_trip(args: ShowTripArgs) -> dict | ToolReply:
        if not built:
            return {"error": "Nothing to show: call build_trip first."}
        plan = built[0]
        state.brief = state.brief.model_copy(update={"plan": plan.summary()})
        return ToolReply(
            result={
                "shown": plan.name,
                "note": "The plan is on screen with a checkout button. Your turn is over.",
            },
            text=args.intro,
            event={
                "type": "trip_plan",
                **plan.view(),
                "summary": chips(state.brief),
                "currency": current_currency.get().view(),
            },
            ends_turn=True,
        )

    return [
        Tool(
            name="search_hotels",
            title="Подбираю отели",
            description=HOTELS_DESCRIPTION,
            args=HotelSearchArgs,
            handler=search_hotels,
            timeout_s=HOTEL_TOOL_TIMEOUT_S,
            preview=lambda r: (
                r.get("error")
                or (
                    f"{r['place']}: {', '.join(h['name'] for h in r['hotels'][:3])}"
                    if r["hotels"]
                    else "Отелей не нашлось"
                )
            ),
        ),
        Tool(
            name="build_trip",
            title="Собираю поездку",
            description=BUILD_DESCRIPTION,
            args=BuildArgs,
            handler=build_trip,
            timeout_s=HOTEL_TOOL_TIMEOUT_S,
            preview=_build_preview,
            then="show_trip",
        ),
        Tool(
            name="show_trip",
            title="Показываю план",
            description=SHOW_DESCRIPTION,
            args=ShowTripArgs,
            handler=show_trip,
            preview=lambda r: r.get("error") or f"План: {r['shown']}",
        ),
    ]
