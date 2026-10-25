from collections.abc import Callable
from datetime import UTC, datetime

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.catalog.catalog import load_catalog
from app.catalog.search import SearchQuery, destination_details, load_snapshots, search
from app.tools.registry import Tool

SEARCH_DESCRIPTION = (
    "Find travel destinations in our catalogue (about 50 places reachable from Moscow) by exact filters: "
    "month, kind of trip, sea and air temperature, flight time, visa for a Russian passport, kids, budget. "
    "Returns the matches with facts (climate for the month, flight hours, visa, price level, highlights, risks) "
    "and near_misses: places that failed exactly one filter, with the reason. Use near_misses to explain "
    "what was excluded and why. Climate comes from Open-Meteo; flights, visas and prices are team estimates "
    "(see sources), so say so when the user relies on them. Flight times are from Moscow only. When the "
    "user asks where a number comes from, name the source from `sources` (e.g. Open-Meteo for climate).\n"
    "Turn the user's words into filters: «тёплое море» means min_sea_temp 24 (relax to 22 only if nothing "
    "matches, and say so); «без долгих перелётов» means max_flight_hours 5 to 6; «недорого» means "
    "max_price_level 1 or 2; «с ребёнком» means with_kids; «без самолёта» means without_flight. A beach or "
    "sea holiday in a named month («на море в ноябре», «beach trip in November») means min_sea_temp 22 or more. "
    "Always pass the month when the user names a time of year.\n"
    "In the answer, after the picks, name 1 to 3 near_misses the user might have expected, with the reason."
)
DETAILS_DESCRIPTION = (
    "Full card of one destination: climate for every month, flight and train time from Moscow, visa, "
    "price level, kids, highlights and risks. Pass the id from search_destinations, or the place name. "
    "The card has no local detail: for which area or beach to choose, where to eat, what to do with kids, "
    "entry documents or transport, call research as well. Don't call it for places search_destinations "
    "just returned: their facts for the month are already there. Use it for a place the user names."
)


class DestinationArgs(BaseModel):
    place: str = Field(description="Destination id from search_destinations (e.g. 'hurghada') or its name.")


def _search_preview(result: dict) -> str:
    names = [m["name"] for m in result["matches"]]
    if names:
        return f"Подходят: {', '.join(names)}"
    near = [m["name"] for m in result["near_misses"]]
    return f"Точных совпадений нет, близко: {', '.join(near)}" if near else "Ничего не подошло"


def catalog_tools(
    sessionmaker: async_sessionmaker[AsyncSession], now: Callable[[], datetime] = lambda: datetime.now(UTC)
) -> list[Tool]:
    catalog = load_catalog()

    async def search_destinations(query: SearchQuery) -> dict:
        async with sessionmaker() as db:
            snapshots = await load_snapshots(db, catalog, now())
        return search(snapshots, query)

    async def get_destination(args: DestinationArgs) -> dict:
        place = catalog.find(args.place)
        if place is None:
            known = ", ".join(p.id for p in catalog.places)
            return {"error": f"Unknown destination {args.place!r}. Known ids: {known}"}
        async with sessionmaker() as db:
            snapshots = await load_snapshots(db, catalog, now())
        return destination_details(next(s for s in snapshots if s.place.id == place.id))

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
