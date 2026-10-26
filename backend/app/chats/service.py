import logging
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime

import anyio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app import agent
from app.catalog.catalog import load_catalog
from app.catalog.search import load_snapshots
from app.chats import repository
from app.flights import DEFAULT_ORIGIN, Flights, city, currency_for, current_origin
from app.llm import LLM
from app.money import current_currency
from app.plan.tools import plan_tools
from app.tools import ToolRegistry
from app.trip import BriefPatch, TripBrief, TripState, merge, trip_tools
from app.trip.brief import chips
from app.trip.freshness import STALE_AFTER, trip_status
from app.trip.refresh import reprice

log = logging.getLogger(__name__)

TITLE_MAX_CHARS = 60
HISTORY_TURNS = 40
AGENT_ERROR_MESSAGE = "Не получилось получить ответ. Попробуйте ещё раз чуть позже."
INTERRUPTED_MESSAGE = "Ответ прерван."
REFRESHED_MESSAGE = "Обновил цены билетов по данным Aviasales. Рядом с ценой видно, как она изменилась."


def title_from(query: str) -> str:
    return query if len(query) <= TITLE_MAX_CHARS else f"{query[: TITLE_MAX_CHARS - 1]}…"


def _load_brief(stored: dict | None) -> TripBrief:
    try:
        return TripBrief.model_validate(stored or {})
    except ValueError:  # saved by an older schema: start the brief over rather than fail the chat
        log.warning("Dropping a trip brief that no longer validates")
        return TripBrief()


def _now() -> datetime:
    return datetime.now(UTC)


def chat_meta(chat: dict, now: datetime | None = None) -> dict:
    meta = {k: v for k, v in chat.items() if k != "brief"}
    return {**meta, **trip_status(_load_brief(chat.get("brief")), now or _now())}


def _last_cards(messages: list[dict]) -> tuple[dict, dict] | None:
    for message in reversed(messages):
        for event in reversed(message["trace"]):
            if event.get("type") == "destinations" and event.get("cards"):
                return message, event
    return None


async def refresh_prices(
    sessionmaker: async_sessionmaker[AsyncSession],
    flights: Flights,
    chat_id: str,
    now: Callable[[], datetime] = _now,
) -> dict | None:
    """The trip's last cards again with fresh tickets, saved as a new reply.
    None when there is nothing to refresh: no cards, prices still fresh (once a day is all the button offers),
    a trip saved before prices were dated, or Aviasales finding no tickets now."""
    moment = now()
    async with sessionmaker() as db:
        found = _last_cards(await repository.list_messages(db, chat_id))
        brief = _load_brief(await repository.get_brief(db, chat_id))
        if (
            found is None
            or not (brief.priced_at and brief.priced_from)
            or moment - brief.priced_at <= STALE_AFTER
        ):
            return None
        snapshots = {s.place.id: s for s in await load_snapshots(db, load_catalog(), moment)}
    _, event = found
    currency = currency_for(brief.priced_from)
    token = current_currency.set(currency)
    try:
        cards = await reprice(event["cards"], brief, snapshots, flights)
        summary = chips(brief)
    finally:
        current_currency.reset(token)
    if not cards:
        return None
    fresh = {"type": "destinations", "summary": summary, "cards": cards, "currency": currency.view()}
    async with sessionmaker() as db:
        saved = await repository.add_message(db, chat_id, "assistant", REFRESHED_MESSAGE, [fresh])
        # read again: a chat turn may have saved the brief while the tickets were loading
        latest = _load_brief(await repository.get_brief(db, chat_id))
        shown = [c["id"] for c in cards]
        priced = latest.model_copy(
            update={"priced_at": moment, "priced_from": brief.priced_from, "shown": shown}
        )
        await repository.save_brief(db, chat_id, priced.model_dump(mode="json"))
        await db.commit()
    return saved


def pick_origin(brief: TripBrief, requested: str | None, known: bool) -> tuple[TripBrief, str]:
    """The city this turn flies from. A city named or picked in this chat wins over the browser's guess,
    unless the user has since picked another one in the browser: then that one is the chat's city."""
    stated = brief.origin_code
    if stated and requested not in (None, stated, brief.origin_over):
        brief = brief.model_copy(update={"origin_code": requested, "origin_over": None})
        stated = requested
    code = stated or requested or DEFAULT_ORIGIN
    return brief.model_copy(update={"origin_guess": not stated and not known}), code


def _final_answer(parts: list[str], failed: bool, finished: bool) -> str:
    if parts:
        return "".join(parts)
    if failed:
        return AGENT_ERROR_MESSAGE
    return "" if finished else INTERRUPTED_MESSAGE


async def stream_reply(
    sessionmaker: async_sessionmaker[AsyncSession],
    llm: LLM,
    chat_id: str,
    query: str,
    origin: str | None = None,
    tools: ToolRegistry | None = None,
    answers: BriefPatch | None = None,
    origin_code: str | None = None,
    flights: Flights | None = None,
    retry: bool = False,
    origin_known: bool = True,
) -> AsyncIterator[dict]:
    # Sessions are opened here, not injected: the stream outlives the request handler.
    async with sessionmaker() as db:
        if retry:
            await repository.drop_failed_turn(db, chat_id)
        title = await repository.ensure_chat(db, chat_id, title_from(query))
        history = await repository.recent_turns(db, chat_id, HISTORY_TURNS)
        trip = TripState(_load_brief(await repository.get_brief(db, chat_id)))
        await repository.add_message(db, chat_id, "user", query)
        await db.commit()
    # the tools search flights from this city and show money in its currency; reset when the turn ends
    requested_code = origin_code
    trip.brief, origin_code = pick_origin(trip.brief, origin_code, origin_known)
    origin_token = current_origin.set(origin_code)
    currency_token = current_currency.set(currency_for(origin_code))
    if answers:
        trip.brief = merge(trip.brief, answers)
        if trip.brief.origin_code and trip.brief.origin_code != origin_code:  # picked on the cards
            origin_code = trip.brief.origin_code
            current_origin.set(origin_code)
            current_currency.set(currency_for(origin_code))
    known_code = requested_code or trip.brief.origin_code
    if known_code and (home := city(origin_code)) and origin and home.name != origin:
        origin = home.name  # the agent is told the city its tickets really fly from
    tools = (tools or ToolRegistry()).extended(
        [*trip_tools(trip, sessionmaker, flights=flights), *plan_tools(trip, sessionmaker, flights=flights)]
    )

    answer_parts: list[str] = []
    trace: list[dict] = []
    failed = finished = False
    try:
        turns = [*history, {"role": "user", "content": query}]
        async for event in agent.run(llm, turns, tools, origin=origin):
            if event["type"] == "assistant_token":
                answer_parts.append(event["text"])
            else:
                trace.append(event)
            yield event
        finished = True
    except Exception:
        log.exception("Agent failed for chat %s", chat_id)
        failed = True
        error = {"type": "error", "message": AGENT_ERROR_MESSAGE}
        trace.append(error)
        yield error
    finally:
        current_origin.reset(origin_token)
        current_currency.reset(currency_token)
        answer = _final_answer(answer_parts, failed, finished)
        # Starlette cancels the stream when the client disconnects; the shield lets the reply still be saved.
        with anyio.CancelScope(shield=True):
            async with sessionmaker() as db:
                await repository.add_message(db, chat_id, "assistant", answer, trace)
                await repository.save_brief(db, chat_id, trip.brief.model_dump(mode="json"))
                await db.commit()
    status = trip_status(trip.brief, _now())
    yield {"type": "done", "answer": answer, "chat_id": chat_id, "title": title, **status}
