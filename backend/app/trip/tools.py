"""The tools that run one chat's trip: keep the brief, ask the missing questions as cards, show destinations.

They are built per chat around a TripState, so whatever the model learns survives until the next turn.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from pydantic import BaseModel, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.catalog.catalog import load_catalog
from app.catalog.search import card, load_snapshots, with_flights
from app.flights import Flights, NoFlights, city, current_origin
from app.tools import Tool, ToolReply
from app.trip.brief import (
    SLOTS,
    BriefPatch,
    Slot,
    TripBrief,
    assumptions,
    chips,
    merge,
    missing,
    prefill,
    search_hint,
)
from app.trip.routes import (
    RoutePlan,
    RouteQuery,
    find_routes,
    plan_of,
    price_route,
    route_card,
    route_for_model,
)

SLOT_TITLES: dict[Slot, str] = {
    "vibe": "Какой отдых хочется?",
    "when": "Когда и на сколько?",
    "travelers": "Кто едет?",
    "route": "Один город или несколько?",
    "budget": "Какой бюджет?",
}
SLOT_NAMES: dict[Slot, str] = {
    "vibe": "тип отдыха",
    "when": "когда",
    "travelers": "кто едет",
    "route": "маршрут",
    "budget": "бюджет",
}

UPDATE_DESCRIPTION = (
    "Call first on every user message about the trip. Pass only what the user said or what follows "
    "unambiguously ('с женой' = 2 adults, 'с ребёнком' = 1 child, 'на неделю' = 7 nights). Never guess "
    "ages, budget or party size. Returns the whole brief, `missing` (what still blocks the search), "
    "`already_asked`, `assumptions` to state if you must go on without answers, and `search_hint` "
    "with filters for search_destinations."
)
ASK_DESCRIPTION = (
    "Show the user cards with the missing questions, all in one go. Only for slots listed in `missing`, "
    "and only once per trip. Ends your turn: the user answers on the cards."
)
SHOW_DESCRIPTION = (
    "Show destinations as cards: single places from search_destinations (pass `id`) and multi-city routes "
    "from search_routes (pass `route`, the city ids in travel order); both can be mixed. The cards already "
    "show the facts (weather, tickets, visa, nights per city), so `why` explains the fit for this user in "
    "their words and `tradeoff` names what they give up. Ends your turn."
)
ROUTES_DESCRIPTION = (
    "Multi-city routes of 2-3 places from our catalogue for when the user wants several cities in one trip "
    "(multi_city in the brief, or words like 'по Европе', 'Ереван и Тбилиси'). The code chains places that "
    "are close to each other and fit the filters, scores how well each route covers the user's interests "
    "(`kinds`), splits the nights, and prices every leg with real Aviasales tickets; short hops are a ground "
    "estimate by distance. Pass the same filters as for search_destinations plus `nights`. Do not offer "
    "routes to families with small children unless they asked for one."
)


@dataclass
class TripState:
    brief: TripBrief
    routes: dict[str, RoutePlan] = field(default_factory=dict)  # found this turn, by id, for the cards


class UpdateArgs(BriefPatch):
    new_trip: bool = Field(False, description="True only when the user starts planning a different trip.")


class Question(BaseModel):
    slot: Slot
    title: str | None = Field(None, max_length=80, description="Short question; omit for the default.")
    hint: str | None = Field(
        None,
        max_length=140,
        description="One short line tying it to the user's words: 'Вы написали «недорого»: это сколько?'",
    )


class AskArgs(BaseModel):
    intro: str = Field(
        max_length=300, description="1-2 friendly sentences: what you understood, why you ask."
    )
    questions: list[Question] = Field(min_length=1, max_length=4)


class Pick(BaseModel):
    id: str | None = Field(None, description="A single place: its id from search_destinations.")
    route: list[str] | None = Field(
        None, min_length=2, max_length=3, description="A route from search_routes: city ids in travel order."
    )
    why: str = Field(max_length=240, description="Why it fits this user, 1-2 short sentences.")
    tradeoff: str | None = Field(None, max_length=140, description="Main downside or risk, one short phrase.")

    @model_validator(mode="after")
    def _one_kind(self):
        if (self.id is None) == (self.route is None):
            raise ValueError("pass either `id` for a place or `route` for a multi-city route")
        return self


class ShowArgs(BaseModel):
    intro: str = Field(max_length=400, description="1-2 sentences above the cards, with any assumptions.")
    picks: list[Pick] = Field(min_length=1, max_length=6)


def _update_preview(result: dict) -> str:
    understood = " · ".join(result["summary"]) or "пока ничего конкретного"
    gaps = [SLOT_NAMES[s] for s in result["missing"]]
    if gaps and not result["already_asked"]:
        return f"Понял: {understood}. Уточню: {', '.join(gaps)}"
    return f"Понял: {understood}"


def trip_tools(
    state: TripState,
    sessionmaker: async_sessionmaker[AsyncSession],
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
    flights: Flights | None = None,
) -> list[Tool]:
    catalog = load_catalog()
    flights = flights or NoFlights()

    async def update_trip_brief(args: UpdateArgs) -> dict:
        base = TripBrief() if args.new_trip else state.brief
        state.brief = merge(base, BriefPatch.model_validate(args.model_dump(exclude={"new_trip"})))
        brief = state.brief
        gaps = missing(brief)
        result = {
            "brief": brief.model_dump(mode="json", exclude_none=True, exclude={"asked", "shown"}),
            "summary": chips(brief),
            "missing": gaps,
            "already_asked": brief.asked,
            "search_hint": search_hint(brief, catalog),
            "shown_before": brief.shown,
        }
        if gaps and brief.asked:
            result["assumptions"] = assumptions(brief)
        return result

    async def ask_user(args: AskArgs) -> dict | ToolReply:
        brief = state.brief
        if brief.asked:
            return {"error": "Already asked once. Do not ask again: go on with `assumptions` and say them."}
        gaps = missing(brief)
        wanted = {q.slot: q for q in args.questions if q.slot in gaps}
        if not wanted:
            return {"error": f"Nothing to ask: missing is {gaps}. Search destinations right away."}
        questions = [
            {"slot": slot, "title": wanted[slot].title or SLOT_TITLES[slot], "hint": wanted[slot].hint}
            for slot in SLOTS
            if slot in wanted
        ]
        state.brief = brief.model_copy(update={"asked": True})
        return ToolReply(
            result={"asked": list(wanted), "note": "The cards are on screen. Your turn is over."},
            text=args.intro,
            event={"type": "clarify", "questions": questions, "prefill": prefill(brief)},
            ends_turn=True,
        )

    async def search_routes(query: RouteQuery) -> dict:
        origin = city(current_origin.get())
        if query.nights is None:
            low, high = state.brief.nights_min, state.brief.nights_max
            query = query.model_copy(update={"nights": high or low})
        async with sessionmaker() as db:
            snapshots = await load_snapshots(db, catalog, now())
        plans = await find_routes(snapshots, query, flights, origin)
        state.routes.update({p.id: p for p in plans})
        if not plans:
            return {
                "routes": [],
                "note": "No 2-3 city route fits. Offer single places from search_destinations.",
            }
        return {
            "from": origin.name if origin else None,
            "routes": [route_for_model(p, query.month) for p in plans],
            "note": "Tickets are the cheapest of the month; the dates of the legs get checked when the trip is "
            "booked. Ground hops are an estimate by distance.",
        }

    async def _route(ids: list[str], snapshots: dict) -> RoutePlan | None:
        places = [catalog.find(i) for i in ids]
        if any(p is None for p in places) or len({p.id for p in places}) != len(places):
            return None
        plan = state.routes.get("+".join(p.id for p in places))
        if plan is None:  # shown on a later turn: rebuild it from the same places, in the same order
            brief = state.brief
            q = RouteQuery(month=brief.month, kinds=brief.kinds, nights=brief.nights_max or brief.nights_min)
            plan = plan_of([snapshots[p.id] for p in places], q)
            await price_route(plan, flights, city(current_origin.get()), brief.month)
        return plan

    async def show_destinations(args: ShowArgs) -> dict | ToolReply:
        async with sessionmaker() as db:
            loaded = await load_snapshots(db, catalog, now())
        picked = {p.id for pick in args.picks if pick.id and (p := catalog.find(pick.id))}
        # the same tickets the search saw: cached by the flights client, so this costs no requests
        await with_flights(
            [s for s in loaded if s.place.id in picked], flights, current_origin.get(), state.brief.month
        )
        snapshots = {s.place.id: s for s in loaded}
        cards, unknown = [], []
        for pick in args.picks:
            if pick.route:
                plan = await _route(pick.route, snapshots)
                if plan is None:
                    unknown.append("+".join(pick.route))
                elif plan.id not in {c["id"] for c in cards}:
                    cards.append(route_card(plan, state.brief.month, pick.why, pick.tradeoff))
                continue
            place = catalog.find(pick.id)
            if place is None:
                unknown.append(pick.id)
            elif place.id not in {c["id"] for c in cards}:
                view = card(snapshots[place.id], state.brief.month)
                cards.append({"type": "place", **view, "why": pick.why, "tradeoff": pick.tradeoff})
        if not cards:
            return {"error": f"Unknown ids {unknown}. Use ids from search_destinations or search_routes."}
        state.brief = state.brief.model_copy(update={"shown": [c["id"] for c in cards]})
        return ToolReply(
            result={"shown": [c["name"] for c in cards], "unknown": unknown, "note": "Cards are on screen."},
            text=args.intro,
            event={"type": "destinations", "summary": chips(state.brief), "cards": cards},
            ends_turn=True,
        )

    return [
        Tool(
            name="update_trip_brief",
            title="Разбираю запрос",
            description=UPDATE_DESCRIPTION,
            args=UpdateArgs,
            handler=update_trip_brief,
            preview=_update_preview,
        ),
        Tool(
            name="ask_user",
            title="Готовлю уточняющие вопросы",
            description=ASK_DESCRIPTION,
            args=AskArgs,
            handler=ask_user,
            preview=lambda r: r.get("error") or f"Спрашиваю: {', '.join(SLOT_NAMES[s] for s in r['asked'])}",
        ),
        Tool(
            name="search_routes",
            title="Собираю маршруты",
            description=ROUTES_DESCRIPTION,
            args=RouteQuery,
            handler=search_routes,
            preview=lambda r: (
                f"Маршруты: {', '.join(x['name'] for x in r['routes'])}"
                if r["routes"]
                else "Маршрутов не нашлось"
            ),
            then="show_destinations",
        ),
        Tool(
            name="show_destinations",
            title="Собираю подборку",
            description=SHOW_DESCRIPTION,
            args=ShowArgs,
            handler=show_destinations,
            preview=lambda r: r.get("error") or f"Показываю: {', '.join(r['shown'])}",
        ),
    ]
