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
from app.destinations import snapshots_by_id
from app.flights import Flights, NoFlights, city, currency_for, current_origin
from app.flights.dictionary import find_city
from app.money import current_currency
from app.tools import Tool, ToolReply
from app.trip.brief import (
    SLOTS,
    BriefPatch,
    Slot,
    TripBrief,
    assumptions,
    cards_first,
    chips,
    merge,
    missing,
    per_night_budget,
    prefill,
    search_hint,
)
from app.trip.routes import (
    RoutePlan,
    RouteQuery,
    find_routes,
    named_route,
    rebuild_route,
    route_card,
    route_for_model,
)

SLOT_TITLES: dict[Slot, str] = {
    "origin": "Откуда летите?",
    "vibe": "Какой отдых хочется?",
    "when": "Когда и на сколько?",
    "travelers": "Кто едет?",
    "route": "Один город или несколько?",
    "budget": "Какой бюджет?",
}
SLOT_NAMES: dict[Slot, str] = {
    "origin": "город вылета",
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
    "`already_asked`, `assumptions` to state if you must go on without answers, `search_hint` "
    "with filters for search_destinations, and `named_place`: the catalogue id of the place the user named."
)
ASK_DESCRIPTION = (
    "Show the user the question cards, once per trip: every slot in `missing` is asked, prefilled with what "
    "the user already said, so they confirm or fix it in one tap. Pass a question only to give it a hint tied "
    "to the user's words. Ends your turn: the user answers on the cards."
)
SHOW_DESCRIPTION = (
    "Show destinations as cards: single places from search_destinations (pass `id`) and multi-city routes "
    "from search_routes (pass `route`, the city ids in travel order); both can be mixed. The cards already "
    "show the facts (weather, tickets, visa, nights per city), so `why` explains the fit for this user in "
    "their words and `tradeoff` names what they give up. Ends your turn."
)
ROUTES_DESCRIPTION = (
    "Multi-city routes of 2 to 7 places from our catalogue for when the user wants several cities in one trip "
    "(multi_city in the brief, or words like 'по Европе', 'Ереван и Тбилиси', 'большой тур'). The code chains "
    "places that are close to each other and fit the filters, orders them without zigzags, scores how well "
    "each route covers the user's interests (`kinds`), splits the nights and prices every leg with real "
    "Aviasales tickets. A bad flight (transfers, no ticket) gets a smarter way: a hub, or a train or bus to a "
    "neighbouring airport (legs with `parts` and `via`; `instead` is the flight it replaced, so you can name "
    "the saving). Hops by land carry real trains (Tutu) or buses (FlixBus) when found (`ground`), else an "
    "estimate. Pass the same filters as for search_destinations plus `nights`; for a big tour pass "
    "min_stops (4-5, or the number the user named, also as max_stops). When the user named the cities "
    "themselves (route_places in the hint), pass them as `places` (order_fixed if they gave the order): the "
    "route is built from exactly those, in the better order. When the user wants trains (by_land in the hint), "
    "pass by_land: hops go by train or bus wherever one runs. Do not offer routes to families with small "
    "children unless they asked for one."
)


# kept for the code, not the model
INTERNAL = {"asked", "shown", "priced_from", "priced_at", "plan", "origin_over", "origin_guess"}


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
    questions: list[Question] = Field(
        default_factory=list,
        max_length=6,
        description="Only to word a card or give it a hint; all are asked.",
    )


class Pick(BaseModel):
    id: str | None = Field(None, description="A single place: its id from search_destinations.")
    route: list[str] | None = Field(
        None, min_length=2, max_length=7, description="A route from search_routes: city ids in travel order."
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


ORIGIN_FIELDS = ("origin", "origin_code", "origin_over", "origin_guess")


def use_origin(code: str):
    """Tickets and money of the rest of this turn come from this city; the chat service resets both after."""
    current_origin.set(code)
    current_currency.set(currency_for(code))
    return city(code)


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

    async def update_trip_brief(args: UpdateArgs) -> dict | ToolReply:
        base = TripBrief() if args.new_trip else state.brief
        if args.new_trip:  # a new trip keeps where the user flies from
            base = base.model_copy(update={k: state.brief.__dict__[k] for k in ORIGIN_FIELDS})
        before = current_origin.get()  # the city this turn has searched from so far
        patch = BriefPatch.model_validate(args.model_dump(exclude={"new_trip"}))
        if (
            patch.origin
            and not base.origin_code
            and (found := find_city(patch.origin))
            and found.code == before
        ):
            # the browser's city echoed back, not something the user said: the cards confirm it instead
            patch = patch.model_copy(update={"origin": None})
        if per_night_budget(patch):  # a hotel price per night is a wish, not what the whole trip may cost
            patch = patch.model_copy(update={"budget_total": None, "budget_currency": None})
        state.brief = merge(base, patch)
        brief = state.brief
        gaps = missing(brief)
        result = {
            "brief": brief.model_dump(mode="json", exclude_none=True, exclude=INTERNAL),
            "summary": chips(brief),
            "missing": gaps,
            "already_asked": brief.asked,
            "search_hint": search_hint(brief, catalog),
            "shown_before": brief.shown,
            "current_plan": brief.plan,
        }
        if gaps and brief.asked:
            result["assumptions"] = assumptions(brief)
        elif gaps:
            result["next"] = (
                "Call ask_user now, before any search or build_trip: the user confirms on the cards."
            )
        if brief.destination and (place := catalog.find(brief.destination)):
            result["named_place"] = place.id
        if args.origin and find_city(args.origin) is None:
            result["origin_unknown"] = f"No airport city {args.origin!r}: ask the user for a nearby one."
        if brief.origin_code and brief.origin_code != before:
            home = use_origin(brief.origin_code)
            result["origin_changed"] = f"Tickets are now searched {home.from_text}."
            # the picker in the browser follows, so the next message comes from the same city
            return ToolReply(result=result, event={"type": "origin", "code": home.code, "name": home.name})
        return result

    async def ask_user(args: AskArgs) -> dict | ToolReply:
        brief = state.brief
        if brief.asked:
            return {"error": "Already asked once. Do not ask again: go on with `assumptions` and say them."}
        gaps = missing(brief)
        if not gaps:
            return {"error": "Nothing to ask: missing is empty. Search destinations right away."}
        # the code decides which cards: every slot in `missing`; the model only words them
        worded = {q.slot: q for q in args.questions}
        questions = [
            {
                "slot": slot,
                "title": (worded[slot].title if slot in worded else None) or SLOT_TITLES[slot],
                "hint": worded[slot].hint if slot in worded else None,
            }
            for slot in SLOTS
            if slot in gaps
        ]
        wanted = [q["slot"] for q in questions]
        state.brief = brief.model_copy(update={"asked": True})
        return ToolReply(
            result={"asked": list(wanted), "note": "The cards are on screen. Your turn is over."},
            text=args.intro,
            event={
                "type": "clarify",
                "questions": questions,
                "prefill": prefill(brief),
                "currency": current_currency.get().view(),
            },
            ends_turn=True,
        )

    async def search_routes(query: RouteQuery) -> dict:
        if refusal := cards_first(state.brief):
            return refusal
        origin = city(current_origin.get())
        if query.nights is None:
            low, high = state.brief.nights_min, state.brief.nights_max
            query = query.model_copy(update={"nights": high or low})
        if query.month is None and state.brief.month:
            query = query.model_copy(update={"month": state.brief.month})
        if state.brief.by_land and not query.by_land:
            query = query.model_copy(update={"by_land": True})
        async with sessionmaker() as db:
            snapshots = await load_snapshots(db, catalog, now())
        if query.places:
            places = [catalog.find(name) for name in query.places]
            if unknown := [n for n, p in zip(query.places, places, strict=True) if p is None]:
                return {"error": f"Not in the catalogue: {unknown}. Use plan_route for these cities."}
            by_id = {s.place.id: s for s in snapshots}
            plans = [await named_route([by_id[p.id] for p in places], query, flights, origin)]
        else:
            plans = await find_routes(snapshots, query, flights, origin)
        state.routes.update({p.id: p for p in plans})
        if not plans:
            again = {"countries": query.countries} if query.countries else {}
            note = "No route fits. Offer single places: call search_destinations with the same month"
            if again:  # the region the user asked for stays: without it the search drifts to other countries
                note += f" and countries={query.countries}"
            return {"routes": [], "note": note + "."}
        return {
            "from": origin.name if origin else None,
            "routes": [route_for_model(p, query.month) for p in plans],
            "note": "Tickets follow the nights of each city where the dates chain. A hop by land shows a real "
            "train or bus when one was found (ground), else an estimate by distance.",
        }

    async def _route(ids: list[str], snapshots: dict) -> RoutePlan | None:
        places = [catalog.find(i) for i in ids]
        if any(p is None for p in places) or len({p.id for p in places}) != len(places):
            return None
        plan = state.routes.get("+".join(p.id for p in places))
        if plan is None:  # shown on a later turn
            stops = [snapshots[p.id] for p in places]
            plan = await rebuild_route(stops, state.brief, flights, city(current_origin.get()))
        return plan

    async def show_destinations(args: ShowArgs) -> dict | ToolReply:
        if refusal := cards_first(state.brief):
            return refusal
        picked = {p.id for pick in args.picks if pick.id and (p := catalog.find(pick.id))}
        async with sessionmaker() as db:
            loaded = list((await snapshots_by_id(db, catalog, now(), picked)).values())
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
        shown = {"shown": [c["id"] for c in cards], "priced_from": current_origin.get(), "priced_at": now()}
        state.brief = state.brief.model_copy(update=shown)
        return ToolReply(
            result={"shown": [c["name"] for c in cards], "unknown": unknown, "note": "Cards are on screen."},
            text=args.intro,
            event={
                "type": "destinations",
                "summary": chips(state.brief),
                "cards": cards,
                "currency": current_currency.get().view(),
            },
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
