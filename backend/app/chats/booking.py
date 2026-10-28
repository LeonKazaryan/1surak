"""A simulated checkout: the plan the agent showed plus the extras the user ticked becomes a booking.

Nothing is paid or reserved anywhere. The booking is a chat message, so it survives a reload and the agent
reads it on the next turn. Prices come from the saved plan, never from the client.
"""

import secrets
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.chats import repository
from app.plan.trip import span_text

NUMBER_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O or 1/I to misread over the phone
NUMBER_LENGTH = 6


class DatesPassed(Exception):
    """The plan starts in the past: it needs new dates, not a booking."""


def _number() -> str:
    return "1S-" + "".join(secrets.choice(NUMBER_ALPHABET) for _ in range(NUMBER_LENGTH))


def _latest_plan(messages: list[dict]) -> tuple[str, dict] | None:
    for message in reversed(messages):
        for event in reversed(message["trace"]):
            if event.get("type") == "trip_plan":
                return message["id"], event
    return None


def _booked(messages: list[dict], message_id: str) -> dict | None:
    return next(
        (
            m
            for m in messages
            for e in m["trace"]
            if e.get("type") == "booking" and e.get("plan_message_id") == message_id
        ),
        None,
    )


async def book(
    sessionmaker: async_sessionmaker[AsyncSession],
    chat_id: str,
    extras: list[str],
    holder: str,
    today: date,
) -> dict | None:
    """The booking message for the trip's latest plan; None when the agent has shown no plan yet."""
    async with sessionmaker() as db:
        messages = await repository.list_messages(db, chat_id)
        found = _latest_plan(messages)
        if found is None:
            return None
        message_id, plan = found
        # shortcut: two clicks at the same moment can both book, fine for one person in a demo
        if existing := _booked(messages, message_id):
            return existing
        dates = plan["dates"]
        if date.fromisoformat(dates["from"]) < today:
            raise DatesPassed
        offered = {c["fix"]["id"]: c["fix"] for c in plan.get("checks", []) if c.get("fix")}
        chosen = [offered[fix_id] for fix_id in dict.fromkeys(extras) if fix_id in offered]
        event = {
            "type": "booking",
            "number": _number(),
            "plan_message_id": message_id,
            "name": plan["name"],
            "dates": dates,
            "holder": holder,
            "extras": chosen,
            "total_rub": plan["costs"]["total"] + sum(fix["price_rub"] for fix in chosen),
            "currency": plan.get("currency"),
        }
        span = span_text(date.fromisoformat(dates["from"]), date.fromisoformat(dates["to"]))
        text = (
            f"Поездка оформлена: {plan['name']}, {span}. Номер брони {event['number']}. "
            "Оплата и бронирование имитируются."
        )
        saved = await repository.add_message(db, chat_id, "assistant", text, [event])
        # the brief keeps the booking in short: the traveller's next trips remember it without reading messages
        brief = await repository.get_brief(db, chat_id) or {}
        booked = {
            "number": event["number"],
            "name": plan["name"],
            "span": span,
            "from": dates["from"],
            "to": dates["to"],
        }
        await repository.save_brief(db, chat_id, {**brief, "booked": booked})
        await db.commit()
    return saved
