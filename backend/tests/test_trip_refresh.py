"""A trip remembers when and from where its prices were found, goes stale, and refreshes without the model."""

import asyncio
import json
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.chats import repository, service
from app.db import init_db
from app.flights import current_origin
from app.tools import ToolRegistry
from app.trip import BriefPatch, TripBrief, TripState, merge, trip_tools
from app.trip.freshness import trip_status
from tests.conftest import FakeFlights, route

NOW = datetime(2026, 10, 26, 12, tzinfo=UTC)
WEEK_AGO = NOW - timedelta(days=7)


def test_should_mark_prices_stale_a_day_after_they_were_found():
    fresh = TripBrief(priced_from="NQZ", priced_at=NOW - timedelta(hours=3))
    old = TripBrief(priced_from="NQZ", priced_at=NOW - timedelta(hours=30))

    assert not trip_status(fresh, NOW)["stale"]
    assert trip_status(old, NOW)["stale"]


def test_should_never_call_a_trip_without_prices_stale():
    assert trip_status(TripBrief(), NOW) == {
        "summary": [],
        "departure": None,
        "priced_at": None,
        "stale": False,
        "dates_passed": False,
    }


def test_should_say_when_the_trip_dates_have_passed():
    november = TripBrief(month=11, priced_at=datetime(2026, 10, 20, tzinfo=UTC))

    assert not trip_status(november, datetime(2026, 11, 15, tzinfo=UTC))["dates_passed"]
    assert trip_status(november, datetime(2026, 12, 2, tzinfo=UTC))["dates_passed"]
    assert trip_status(TripBrief(date_from=date(2026, 10, 20)), NOW)["dates_passed"]


def test_should_describe_the_trip_and_where_it_flies_from():
    brief = merge(TripBrief(), BriefPatch(destination="Казань", month=1, nights_min=2))
    status = trip_status(brief.model_copy(update={"priced_from": "NQZ", "priced_at": NOW}), NOW)

    assert status["summary"][:2] == ["Казань", "Январь · 2 ночи"]
    assert status["departure"] == "из Астаны"
    assert status["priced_at"] == NOW.isoformat()


async def _scenario(
    db_url: str,
    picks: list[dict],
    before: FakeFlights,
    after: FakeFlights,
    shown_at=WEEK_AGO,
    later: dict | None = None,
    **fields,
):
    """Show cards at `shown_at` with `before` prices, save the chat (with `later` changes to the brief),
    then refresh it with `after` prices."""
    engine = create_async_engine(db_url, poolclass=NullPool)
    await init_db(engine)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    state = TripState(merge(TripBrief(), BriefPatch(**fields)))
    tools = ToolRegistry(trip_tools(state, maker, now=lambda: shown_at, flights=before))
    token = current_origin.set("NQZ")
    try:
        shown = await tools.execute("show_destinations", json.dumps({"intro": "Вот", "picks": picks}))
    finally:
        current_origin.reset(token)
    chat_id = str(uuid4())
    async with maker() as db:
        await repository.ensure_chat(db, chat_id, "Поездка")
        await repository.add_message(db, chat_id, "assistant", "Вот", [shown.event])
        brief = state.brief.model_copy(update=later or {})
        await repository.save_brief(db, chat_id, brief.model_dump(mode="json"))
        await db.commit()
    message = await service.refresh_prices(maker, after, chat_id, now=lambda: NOW)
    async with maker() as db:
        saved = await repository.list_messages(db, chat_id)
        brief = TripBrief.model_validate(await repository.get_brief(db, chat_id))
    await engine.dispose()
    return message, saved, brief


def test_should_refresh_the_shown_prices_without_asking_the_model(db_url):
    picks = [{"id": "hurghada", "why": "Тёплое море", "tradeoff": "Ветрено"}]
    before = FakeFlights({"HRG": route(330, price=12_775)})
    after = FakeFlights({"HRG": route(330, price=13_101)})

    message, saved, brief = asyncio.run(_scenario(db_url, picks, before, after, kinds=["sea"], month=11))

    assert message["role"] == "assistant" and message["content"].startswith("Обновил цены")
    [event] = [e for e in message["trace"] if e["type"] == "destinations"]
    [card] = event["cards"]
    assert card["flight"]["price_rub"] == 13_101
    assert (card["why"], card["tradeoff"]) == ("Тёплое море", "Ветрено")
    assert card["price_change"] == {"rub": 326, "since": WEEK_AGO.isoformat()}
    assert after.asked[0][0] == "NQZ"  # from the city the trip was priced from
    assert event["currency"]["code"] == "KZT"
    assert [m["id"] for m in saved][-1] == message["id"]
    assert brief.priced_at == NOW and brief.priced_from == "NQZ"


def test_should_refresh_a_route_and_its_total(db_url):
    picks = [{"route": ["yerevan", "tbilisi"], "why": "Два города"}]
    before = FakeFlights(
        {"EVN": route(240, price=30_000), "TBS": route(250, price=20_000), "NQZ": route(200)}
    )
    after = FakeFlights({"EVN": route(240, price=31_000), "TBS": route(250, price=20_000), "NQZ": route(200)})
    fields = {"kinds": ["city"], "month": 10, "nights_min": 6, "adults": 2, "multi_city": True}

    message, _, _ = asyncio.run(_scenario(db_url, picks, before, after, **fields))

    [card] = next(e for e in message["trace"] if e["type"] == "destinations")["cards"]
    assert card["type"] == "route" and card["why"] == "Два города"
    assert [s["id"] for s in card["stops"]] == ["yerevan", "tbilisi"]
    assert card["price_change"]["rub"] == 1_000


def test_should_keep_the_nights_of_a_route_when_the_brief_changed_since(db_url):
    picks = [{"route": ["yerevan", "tbilisi"], "why": "Два города"}]
    flights = FakeFlights({"EVN": route(240), "TBS": route(250), "NQZ": route(200)})
    fields = {"kinds": ["city"], "month": 10, "nights_min": 6, "adults": 2, "multi_city": True}

    message, _, _ = asyncio.run(
        _scenario(db_url, picks, flights, flights, later={"nights_min": 12}, **fields)
    )

    [card] = next(e for e in message["trace"] if e["type"] == "destinations")["cards"]
    assert sum(s["nights"] for s in card["stops"]) == 6


def test_should_keep_the_old_prices_when_aviasales_finds_no_tickets(db_url):
    picks = [{"id": "hurghada", "why": "Тёплое море"}]
    before = FakeFlights({"HRG": route(330, price=12_775)})

    message, saved, brief = asyncio.run(
        _scenario(db_url, picks, before, FakeFlights(), kinds=["sea"], month=11)
    )

    assert message is None and len(saved) == 1
    assert brief.priced_at == WEEK_AGO  # still stale, so the banner stays


def test_should_not_refresh_a_trip_saved_before_prices_were_dated(db_url):
    picks = [{"id": "hurghada", "why": "Тёплое море"}]
    flights = FakeFlights({"HRG": route(330)})
    undated = {"priced_from": None, "priced_at": None}

    message, _, _ = asyncio.run(
        _scenario(db_url, picks, flights, flights, later=undated, kinds=["sea"], month=11)
    )

    assert message is None


def test_should_not_refresh_prices_that_are_still_fresh(db_url):
    picks = [{"id": "hurghada", "why": "Тёплое море"}]
    flights = FakeFlights({"HRG": route(330, price=12_775)})

    message, saved, _ = asyncio.run(
        _scenario(db_url, picks, flights, flights, shown_at=NOW - timedelta(hours=2), kinds=["sea"], month=11)
    )

    assert message is None and len(saved) == 1


def test_should_have_nothing_to_refresh_before_any_cards(db_url):
    async def scenario():
        engine = create_async_engine(db_url, poolclass=NullPool)
        await init_db(engine)
        maker = async_sessionmaker(engine, expire_on_commit=False)
        chat_id = str(uuid4())
        async with maker() as db:
            await repository.ensure_chat(db, chat_id, "Пусто")
            await db.commit()
        result = await service.refresh_prices(maker, FakeFlights(), chat_id)
        await engine.dispose()
        return result

    assert asyncio.run(scenario()) is None
