"""When Aviasales' cache has no ticket to a small city: the way there through its country's main airport.

The Data API only knows prices someone searched lately, so Astana-Mekele has none while the website finds
78 000 ₽ with a change. Two answers instead of «no tickets»: a link to the live search on Aviasales, and two
cached tickets through the main airport (Astana-Addis Ababa, Addis Ababa-Mekele) that can be flown in a row,
or, when no pair of days connects, their prices added up and marked as an estimate.
"""

from app.catalog.search import Snapshot
from app.flights import Flights, city, city_code
from app.flights.client import search_link
from app.flights.connections import connect, through_hub
from app.flights.network import Network
from app.money import money

MAX_GATEWAYS = 6  # cities a search prices this way: two cached lookups each


def gateway(code: str, network: Network) -> str | None:
    """The best connected airport of the city's country, when that is another city."""
    from app.destinations import country_cities

    c = city(code)
    found = country_cities([c.country], network, per_country=1) if c else []
    return found[0] if found and found[0] != c.code else None


async def via_gateway(
    origin: str, s: Snapshot, flights: Flights, network: Network, month: int | None
) -> dict | None:
    hub = gateway(s.place.airport, network)
    if hub is None or hub == city_code(origin):
        return None
    first = (await flights.routes(origin, [hub], month)).get(hub)
    second = (await flights.routes(hub, [s.place.airport], month)).get(s.place.airport)
    if not first or not second:
        return None
    hub_city = city(hub)
    pair = connect(hub_city, first, second, lambda price, minutes, transfers: price)
    where = hub_city.name_in or hub_city.name  # «в Аддис-Абебе»
    if pair:
        return {**pair.view(), "via_in": where, "price": money(pair.price), "estimate": False}
    total = first.cheapest.price + second.cheapest.price
    return {
        "via": hub_city.name,
        "via_in": where,
        "price_rub": total,
        "price": money(total),
        "estimate": True,  # the two cheapest days do not connect: a rough sum, dates to be matched
        "separate_tickets": True,
        "tickets": [first.cheapest.view(), second.cheapest.view()],
    }


async def via_hub(origin: str, s: Snapshot, flights: Flights, network: Network) -> dict | None:
    """No fare on any day, not even through the country's main airport: two tickets through a world hub both
    ends fly to directly (Astana → Dubai → Harare), their nearest-dates prices added up as an estimate."""
    found = await through_hub(origin, s.place.airport, flights, network)
    if found is None:
        return None
    return {
        "via": found.hub.name,
        "via_in": found.where,
        "price_rub": found.price,
        "price": money(found.price),
        "estimate": True,  # nearest-dates prices: the days are matched when the tickets are bought
        "separate_tickets": True,
        "tickets": [found.first.view(), found.second.view()],
    }


async def fill_missing(
    snapshots: list[Snapshot], origin: str, flights: Flights, network: Network, month: int | None
) -> None:
    """Search links for every place without a cached ticket, and a price to plan with: two tickets through the
    country's main airport for route-map cities, else through a world hub."""
    tried = 0
    for s in snapshots:
        if s.flights or not s.place.airport:
            continue
        s.search_link = search_link(origin, s.place.airport, month)
        if tried < MAX_GATEWAYS:
            tried += 1
            gateway_way = None if s.place.verified else await via_gateway(origin, s, flights, network, month)
            s.via = gateway_way or await via_hub(origin, s, flights, network)
