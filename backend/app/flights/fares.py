"""The fares table: what Aviasales answered for a city pair and month, kept until it expires.

One row per (origin, destination, month), the summary only (cheapest, direct, fastest), not every ticket.
"""

import logging
from dataclasses import asdict
from datetime import UTC, datetime

from sqlalchemy import delete, insert, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import fares
from app.flights.client import FareKey, RouteFlights, Ticket

log = logging.getLogger(__name__)

SOURCE = "aviasales-data-api"


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _ticket(data: dict | None) -> Ticket | None:
    return Ticket(**data) if data else None


def to_row(key: FareKey, found: RouteFlights | None, fetched_at: datetime, expires_at: datetime) -> dict:
    tickets = (
        {
            "cheapest": asdict(found.cheapest),
            "direct": asdict(found.direct) if found.direct else None,
            "fastest": asdict(found.fastest),
        }
        if found
        else {}
    )
    return {
        "origin": key[0],
        "destination": key[1],
        "month": key[2],
        "price_rub": found.cheapest.price if found else None,
        "direct_price_rub": found.direct.price if found and found.direct else None,
        "duration_min": found.duration_min if found else None,
        "tickets": tickets,
        "source": SOURCE,
        "fetched_at": fetched_at,
        "expires_at": expires_at,
    }


def from_row(row) -> RouteFlights | None:
    t = row.tickets or {}
    if not t.get("cheapest"):
        return None
    return RouteFlights(
        cheapest=_ticket(t["cheapest"]), direct=_ticket(t.get("direct")), fastest=_ticket(t["fastest"])
    )


async def load_fares(
    db: AsyncSession, keys: list[FareKey], now: datetime
) -> dict[FareKey, tuple[datetime, RouteFlights | None]]:
    """The rows still valid at `now`, with their expiry."""
    if not keys:
        return {}
    query = select(fares).where(
        tuple_(fares.c.origin, fares.c.destination, fares.c.month).in_(keys), fares.c.expires_at > now
    )
    return {
        (row.origin, row.destination, row.month): (_aware(row.expires_at), from_row(row))
        for row in (await db.execute(query)).all()
    }


async def save_fares(db: AsyncSession, rows: list[dict]) -> None:
    for row in rows:
        await db.execute(
            delete(fares).where(
                fares.c.origin == row["origin"],
                fares.c.destination == row["destination"],
                fares.c.month == row["month"],
            )
        )
    if rows:
        await db.execute(insert(fares), rows)


class FareStore:
    """The fares table behind one sessionmaker. A database failure means «not cached», never an error."""

    def __init__(self, sessionmaker):
        self._sessionmaker = sessionmaker

    async def load(
        self, keys: list[FareKey], now: datetime
    ) -> dict[FareKey, tuple[datetime, RouteFlights | None]]:
        try:
            async with self._sessionmaker() as db:
                return await load_fares(db, keys, now)
        except Exception:
            log.warning("Could not read cached fares", exc_info=True)
            return {}

    async def save(
        self, found: dict[FareKey, RouteFlights | None], fetched_at: datetime, expires_at: datetime
    ) -> None:
        rows = [to_row(key, result, fetched_at, expires_at) for key, result in found.items()]
        try:
            async with self._sessionmaker() as db:
                await save_fares(db, rows)
                await db.commit()
        except Exception:
            log.warning("Could not save %d fares", len(rows), exc_info=True)
