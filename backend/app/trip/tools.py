"""The tools that run one chat's trip: keep the brief, ask the missing questions as cards, show destinations.

They are built per chat around a TripState, so whatever the model learns survives until the next turn.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.catalog.catalog import load_catalog
from app.catalog.search import card, load_snapshots
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

SLOT_TITLES: dict[Slot, str] = {
    "vibe": "Какой отдых хочется?",
    "when": "Когда и на сколько?",
    "travelers": "Кто едет?",
    "budget": "Какой бюджет?",
}
SLOT_NAMES: dict[Slot, str] = {
    "vibe": "тип отдыха",
    "when": "когда",
    "travelers": "кто едет",
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
    "Show destinations from search_destinations as cards. The cards already show the facts (weather, "
    "flight, visa, price level), so `why` explains the fit for this user in their words and `tradeoff` "
    "names what they give up. Ends your turn."
)


@dataclass
class TripState:
    brief: TripBrief


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
    id: str = Field(description="Destination id from search_destinations.")
    why: str = Field(max_length=240, description="Why it fits this user, 1-2 short sentences.")
    tradeoff: str | None = Field(None, max_length=140, description="Main downside or risk, one short phrase.")


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
) -> list[Tool]:
    catalog = load_catalog()

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

    async def show_destinations(args: ShowArgs) -> dict | ToolReply:
        async with sessionmaker() as db:
            snapshots = {s.place.id: s for s in await load_snapshots(db, catalog, now())}
        cards, unknown = [], []
        for pick in args.picks:
            place = catalog.find(pick.id)
            if place is None:
                unknown.append(pick.id)
            elif place.id not in {c["id"] for c in cards}:
                view = card(snapshots[place.id], state.brief.month)
                cards.append({**view, "why": pick.why, "tradeoff": pick.tradeoff})
        if not cards:
            return {"error": f"Unknown ids {unknown}. Use ids from search_destinations."}
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
            name="show_destinations",
            title="Собираю подборку",
            description=SHOW_DESCRIPTION,
            args=ShowArgs,
            handler=show_destinations,
            preview=lambda r: r.get("error") or f"Показываю: {', '.join(r['shown'])}",
        ),
    ]
