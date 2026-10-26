"""The tools that turn a pick into a trip: build_trip assembles it in code, show_trip puts it on screen
with the agent's own words. Built per chat around the same TripState as the trip tools."""

from collections.abc import Callable
from datetime import UTC, datetime

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.catalog.catalog import load_catalog
from app.catalog.search import load_snapshots
from app.flights import Flights, NoFlights, city, current_origin
from app.money import current_currency
from app.plan.assemble import assemble
from app.plan.trip import TripPlan
from app.tools import Tool, ToolReply
from app.trip.brief import cards_first, chips
from app.trip.tools import TripState

MAX_STOPS = 3

BUILD_DESCRIPTION = (
    "Assemble the whole trip for what the user picked: tickets on dates that follow the nights, a hotel for this "
    "party with reasons, misses and alternatives, transfers, connection checks (landing vs check-in, check-out vs "
    "the flight home), a day-by-day plan with real sights and local food, and the bill against the budget. "
    "Pass `id`: a place id or a route id ('tbilisi+yerevan') from shown_before or current_plan. To change the "
    "hotel pass `hotels` with ids from the plan's alternatives. Always follow with show_trip."
)
SHOW_DESCRIPTION = (
    "Show the plan from build_trip on screen, with a checkout button. `intro` is what you say as the travel "
    "agent who put it together. Ends your turn."
)


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
) -> list[Tool]:
    catalog = load_catalog()
    flights = flights or NoFlights()
    built: list[TripPlan] = []  # this turn's plan, for show_trip

    async def build_trip(args: BuildArgs) -> dict:
        if refusal := cards_first(state.brief):
            return refusal
        ids = [part.strip() for part in args.id.split("+") if part.strip()]
        places = [catalog.find(i) for i in ids]
        if not 0 < len(places) <= MAX_STOPS or None in places or len({p.id for p in places}) != len(places):
            return {"error": f"Unknown id {args.id!r}: pass a place id or a route id from shown_before."}
        async with sessionmaker() as db:
            snapshots = {s.place.id: s for s in await load_snapshots(db, catalog, now())}
        asked = {h.rsplit("-h", 1)[0]: h for h in args.hotels or []}
        plan = await assemble(
            [snapshots[p.id] for p in places],
            state.brief,
            flights,
            city(current_origin.get()),
            now().date(),
            prefer=asked,
            previous=state.brief.plan,
        )
        built[:] = [plan]
        result = plan.for_model()
        if notes := _hotel_notes(plan, asked):
            result["hotel_notes"] = notes
        return result

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
            name="build_trip",
            title="Собираю поездку",
            description=BUILD_DESCRIPTION,
            args=BuildArgs,
            handler=build_trip,
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
