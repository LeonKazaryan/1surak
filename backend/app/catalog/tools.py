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
    "(see sources), so say so when the user relies on them. Flight times are from Moscow only."
)
DETAILS_DESCRIPTION = (
    "Full card of one destination: climate for every month, flight and train time from Moscow, visa, "
    "price level, kids, highlights and risks. Pass the id from search_destinations, or the place name."
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
