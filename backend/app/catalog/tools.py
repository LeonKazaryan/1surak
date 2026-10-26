from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.catalog.catalog import load_catalog
from app.catalog.search import (
    SearchQuery,
    Snapshot,
    destination_details,
    failures,
    in_scope,
    load_snapshots,
    search,
    with_flights,
)
from app.destinations import load_discovered, reachable, snapshots_by_id
from app.flights import Flights, NoFlights, city, current_origin
from app.flights.network import network
from app.tools.registry import Tool

if TYPE_CHECKING:
    from app.destinations.climate import ClimateFetcher

SEARCH_DESCRIPTION = (
    "Find travel destinations in our catalogue (about 50 places) by exact filters: month, kind of trip, sea "
    "and air temperature, flight time, direct flights, ticket price, visa for a Russian passport, kids, budget. "
    "Flights are real Aviasales tickets from the user's departure city: `flight` has the cheapest one-way "
    "ticket (price, airline, transfers, hours, date) and a direct option when there is one. Returns the "
    "matches with facts (climate for the month, flight, visa, price level, highlights, risks) and "
    "near_misses: places that failed exactly one filter, with the reason. Use near_misses to explain what "
    "was excluded and why. Climate comes from Open-Meteo, tickets from Aviasales (found in the last days, "
    "not a live search); visas and price levels are team estimates (see sources). When the "
    "user asks where a number comes from, name the source from `sources` (e.g. Open-Meteo for climate).\n"
    "Turn the user's words into filters: «тёплое море» means min_sea_temp 24 (relax to 22 only if nothing "
    "matches, and say so); «без долгих перелётов» means max_flight_hours 5 to 6; «недорого» means "
    "max_price_level 1 or 2; «с ребёнком» means with_kids; «без самолёта» means without_flight. A beach or "
    "sea holiday in a named month («на море в ноябре», «beach trip in November») means min_sea_temp 22 or more. "
    "Always pass the month when the user names a time of year.\n"
    "In the answer, after the picks, name 1 to 3 near_misses the user might have expected, with the reason."
)
DETAILS_DESCRIPTION = (
    "Full card of one destination: climate for every month, real tickets from the user's city, visa, "
    "price level, kids, highlights and risks. Pass the id from search_destinations, or the place name. "
    "The card has no local detail: for which area or beach to choose, where to eat, what to do with kids, "
    "entry documents or transport, call research as well. Don't call it for places search_destinations "
    "just returned: their facts for the month are already there. Use it for a place the user names."
)


class DestinationArgs(BaseModel):
    place: str = Field(
        max_length=80, description="Destination id from search_destinations (e.g. 'hurghada') or its name."
    )


def _search_preview(result: dict) -> str:
    names = [m["name"] for m in result["matches"]]
    if names:
        return f"Подходят: {', '.join(names)}"
    near = [m["name"] for m in result["near_misses"]]
    return f"Точных совпадений нет, близко: {', '.join(near)}" if near else "Ничего не подошло"


MAX_PRICED = 12  # route-map cities that get real tickets in one search, the closest that fit everything else
TICKET_MISSES = {"flight", "direct", "ticket", "train"}


def shortlist(discovered: list[Snapshot], q: SearchQuery) -> list[Snapshot]:
    """The route-map cities worth pricing: in scope and failing nothing but the ticket filters, nearest first
    (reachable() already orders them by distance)."""
    fits = [s for s in discovered if in_scope(s, q) and all(m.kind in TICKET_MISSES for m in failures(s, q))]
    return fits[:MAX_PRICED]


def catalog_tools(
    sessionmaker: async_sessionmaker[AsyncSession],
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
    flights: Flights | None = None,
    climate: "ClimateFetcher | None" = None,
) -> list[Tool]:
    catalog = load_catalog()
    flights = flights or NoFlights()

    async def search_destinations(query: SearchQuery) -> dict:
        origin = current_origin.get()
        reach = reachable(network(), origin)
        async with sessionmaker() as db:
            snapshots = await load_snapshots(db, catalog, now())
            discovered = await load_discovered(db, reach, now())
        pending = await climate.ensure(reach) if climate else 0  # their climate arrives for the next search
        snapshots = await with_flights(
            [*snapshots, *shortlist(discovered, query)], flights, origin, query.month, query
        )
        result = search(snapshots, query, city(origin))
        result["route_map"] = {
            "cities_with_direct_flights": len(reach),
            "looked_at": len(discovered),
            "climate_still_loading": pending,
        }
        return result

    async def get_destination(args: DestinationArgs) -> dict:
        place = catalog.find(args.place)
        if place is None:
            known = ", ".join(p.id for p in catalog.places)
            return {"error": f"Unknown destination {args.place!r}. Known ids: {known}"}
        async with sessionmaker() as db:
            snapshot = (await snapshots_by_id(db, catalog, now(), [place.id]))[place.id]
        await with_flights([snapshot], flights, current_origin.get(), None)
        return destination_details(snapshot)

    return [
        Tool(
            name="search_destinations",
            title="Подбираю направления",
            description=SEARCH_DESCRIPTION,
            args=SearchQuery,
            handler=search_destinations,
            preview=_search_preview,
            then="show_destinations",
        ),
        Tool(
            name="get_destination",
            title="Изучаю направление",
            description=DETAILS_DESCRIPTION,
            args=DestinationArgs,
            handler=get_destination,
            preview=lambda r: r.get("error") or f"{r['name']}, {r['country']}",
        ),
    ]
