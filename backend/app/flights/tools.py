from pydantic import BaseModel, Field

from app.flights import Flights, city, current_origin
from app.flights.dictionary import cities, rub
from app.tools.registry import Tool

DESCRIPTION = (
    "Real Aviasales tickets for one route, from the user's departure city unless `origin` is given: the cheapest "
    "one-way ticket and the cheapest direct one, with airline, transfers, hours, departure and a link to buy. "
    "Use it for a city outside our catalogue, for legs of a multi-city trip, or when the user asks about "
    "prices or direct flights. Prices are found by Aviasales users in the last days, not a live search."
)


class FlightArgs(BaseModel):
    destination: str = Field(description="City name in Russian or IATA code: 'Стамбул' or 'IST'.")
    month: int | None = Field(None, ge=1, le=12, description="Travel month; omit for the nearest dates.")
    origin: str | None = Field(None, description="Only for a leg that starts elsewhere: city name or IATA.")


def resolve(name: str | None):
    if not name:
        return None
    found = city(name)
    if found:
        return found
    needle = name.strip().casefold()
    return next((c for c in cities().values() if c.name.casefold() == needle), None)


def flight_tools(flights: Flights) -> list[Tool]:
    async def search_flights(args: FlightArgs) -> dict:
        origin = resolve(args.origin) if args.origin else city(current_origin.get())
        destination = resolve(args.destination)
        if origin is None or destination is None:
            return {"error": f"Unknown city: {args.origin if origin is None else args.destination!r}"}
        found = await flights.route(origin.code, destination.code, args.month)
        result = {"from": origin.name, "to": destination.name}
        if found is None:
            return {**result, "tickets": None, "note": "Aviasales has no tickets for this route and dates."}
        return {**result, "tickets": found.view()}

    def preview(result: dict) -> str:
        if result.get("error"):
            return result["error"]
        ticket = result.get("tickets")
        if not ticket:
            return f"{result['from']} → {result['to']}: билетов не нашлось"
        stops = "прямой" if ticket["transfers"] == 0 else f"пересадок: {ticket['transfers']}"
        return f"{result['from']} → {result['to']}: от {rub(ticket['price_rub'])}, {stops}"

    return [
        Tool(
            name="search_flights",
            title="Ищу билеты",
            description=DESCRIPTION,
            args=FlightArgs,
            handler=search_flights,
            preview=preview,
        )
    ]
