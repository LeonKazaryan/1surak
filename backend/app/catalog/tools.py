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
from app.destinations import candidates, country_cities, in_countries, load_discovered, snapshots_by_id
from app.destinations.gateway import fill_missing
from app.destinations.live import Directions, NoDirections
from app.flights import Flights, NoFlights, city, current_origin
from app.flights.network import network
from app.tools.registry import Tool, fact
from app.visas import fees

if TYPE_CHECKING:
    from app.destinations.climate import ClimateFetcher

SEARCH_DESCRIPTION = (
    "Find travel destinations among the hand-checked places and every city the user's flights reach (thousands, "
    "climate from Open-Meteo) by exact filters: month, kind of trip, sea "
    "and air temperature, flight time, direct flights, ticket price, visa for the user's passport (the "
    "departure country's, Passport Index), kids, budget. "
    "Flights are real tickets from the user's departure city: `flight` has the cheapest one-way "
    "ticket (price, airline, transfers, hours, date) and a direct option when there is one. Returns the "
    "matches with facts (climate for the month, flight, visa, price level, highlights, risks) and "
    "near_misses: places that failed exactly one filter, with the reason. Use near_misses to explain what "
    "was excluded and why. Climate comes from Open-Meteo, tickets that travellers found (in the last days, "
    "not a live search); visas are the Passport Index rules for the user's passport, with the fee when "
    "it was already found on the web; price levels are team estimates (see sources). Never filter by visa "
    "(visa) unless the user asked for «без визы»: a visa is shown on the card, it is not a reason to drop a "
    "country the user named. When the "
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


def _search_facts(result: dict) -> list[dict]:
    reach = (result.get("route_map") or {}).get("destinations_from_your_city") or 0
    fit = len(result.get("matches") or []) + (result.get("more_matches") or 0)
    found = [fact(reach, ("направление", "направления", "направлений"), "из города")] if reach else []
    if result.get("checked"):
        found.append(fact(result["checked"], ("место", "места", "мест"), "проверил"))
    return [*found, fact(fit, ("подходит", "подходят", "подходят"))]


SEARCH_TIMEOUT_S = 45.0  # live destinations, a few climates and the tickets
FETCH_NOW = 8  # route-map cities of the asked region whose climate a search fetches before answering
MAX_PRICED = 12
MAX_NEAR = 4  # route-map cities shown as near misses, with the one filter they fail  # route-map cities that get real tickets in one search, the closest that fit everything else
TICKET_MISSES = {"flight", "direct", "ticket", "train"}


def shortlist(discovered: list[Snapshot], q: SearchQuery) -> list[Snapshot]:
    """The route-map cities worth pricing: the closest that fail nothing but the ticket filters, and a few
    that miss by exactly one more (dearer, a visa), so «Германия, недорого» shows Frankfurt as a near miss
    with its reason instead of nothing at all. Live destinations come first in `discovered`."""
    fits, near = [], []
    for s in discovered:
        if not in_scope(s, q):
            continue
        other = [m for m in failures(s, q) if m.kind not in TICKET_MISSES]
        if not other:
            fits.append(s)
        elif len(other) == 1:
            near.append(s)
    return fits[:MAX_PRICED] + near[:MAX_NEAR]


def catalog_tools(
    sessionmaker: async_sessionmaker[AsyncSession],
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
    flights: Flights | None = None,
    climate: "ClimateFetcher | None" = None,
    directions: Directions | None = None,
) -> list[Tool]:
    catalog = load_catalog()
    flights = flights or NoFlights()

    async def search_destinations(query: SearchQuery) -> dict:
        origin = current_origin.get()
        live = await (directions or NoDirections()).destinations(origin)
        # the countries the user named come first: their main cities, even with no flight from home
        named = country_cities(query.countries, network())
        reach = candidates([*named, *live], network(), origin)
        fetched = 0
        if climate:
            # the first cities of the asked region with no climate yet are fetched now, not on the next search
            missing = await climate.missing(in_countries(reach, query.countries))
            fetched = await climate.fetch_now(missing[:FETCH_NOW])
        async with sessionmaker() as db:
            snapshots = await load_snapshots(db, catalog, now())
            discovered = await load_discovered(db, reach, now())
        pending = await climate.ensure(reach) if climate else 0  # the rest arrive for the next search
        snapshots = await with_flights(
            [*snapshots, *shortlist(discovered, query)], flights, origin, query.month, query
        )
        # no cached ticket: a live search link, and two tickets through the country's main airport
        shown = [s for s in snapshots if in_scope(s, query)]
        await fill_missing(shown, origin, flights, network(), query.month)
        result = search(snapshots, query, city(origin))
        # the fees of the visas these places need start loading now: the cards come a step later
        shown_ids = {m["id"] for m in result.get("matches", [])}
        await fees().warm(s.visa for s in snapshots if s.place.id in shown_ids)
        result["route_map"] = {
            "destinations_from_your_city": len(reach),
            "live_from_aviasales": len(live),
            "looked_at": len(discovered),
            "climate_fetched_now": fetched,
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
            facts=_search_facts,
            then="show_destinations",
            timeout_s=SEARCH_TIMEOUT_S,
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
