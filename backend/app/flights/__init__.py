from contextvars import ContextVar

from app.flights.client import Flights, NoFlights, RouteFlights, Ticket, TravelpayoutsFlights
from app.flights.dictionary import City, city, nearest

DEFAULT_ORIGIN = "MOW"
# The departure city of the request being answered. Set by the chat service, read by the tools,
# so a tool registry built once at startup still searches from each user's own city.
current_origin: ContextVar[str] = ContextVar("current_origin", default=DEFAULT_ORIGIN)

__all__ = [
    "DEFAULT_ORIGIN",
    "City",
    "Flights",
    "NoFlights",
    "RouteFlights",
    "Ticket",
    "TravelpayoutsFlights",
    "city",
    "current_origin",
    "nearest",
]
