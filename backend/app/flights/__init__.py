from contextvars import ContextVar

from app.flights.client import Flights, NoFlights, RouteFlights, Ticket, TravelpayoutsFlights
from app.flights.dictionary import City, city, city_code, nearest
from app.flights.network import Link, Network, network
from app.money import Currency, currency_of

DEFAULT_ORIGIN = "MOW"
# The departure city of the request being answered. Set by the chat service, read by the tools,
# so a tool registry built once at startup still searches from each user's own city.
current_origin: ContextVar[str] = ContextVar("current_origin", default=DEFAULT_ORIGIN)


def currency_for(origin_code: str | None) -> Currency:
    found = city(origin_code)
    return currency_of(found.country if found else None)


__all__ = [
    "DEFAULT_ORIGIN",
    "City",
    "Flights",
    "Link",
    "Network",
    "NoFlights",
    "RouteFlights",
    "Ticket",
    "TravelpayoutsFlights",
    "city",
    "city_code",
    "currency_for",
    "current_origin",
    "nearest",
    "network",
]
