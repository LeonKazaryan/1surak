from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.catalog.catalog import load_catalog
from app.flights import Flights, city, current_origin, network
from app.flights.dictionary import cities, rub
from app.flights.planner import MAX_OPEN_STOPS, Request, Stop, plan, resolve_stop
from app.tools.registry import Tool

DESCRIPTION = (
    "Real Aviasales tickets for one route, from the user's departure city unless `origin` is given: the cheapest "
    "one-way ticket and the cheapest direct one, with airline, transfers, hours, departure and a link to buy. "
    "Use it for a city outside our catalogue, or when the user asks about prices or direct flights on one "
    "route. For a trip through several cities use plan_route. Prices are found by Aviasales users in the "
    "last days, not a live search."
)
PLAN_DESCRIPTION = (
    "Plan a trip through several cities from the user's departure city: prices every leg as a one-way "
    "Aviasales ticket and returns ranked plans with legs, total price and travel time. With order_fixed=false "
    "it finds the best order of the stops (up to 5). Legs without a price say whether the route map has a "
    "direct flight and the estimated hours; places without an airport (Суздаль, Анапа) go by train from "
    "Moscow. A leg may have `cheaper_via`: two tickets through a hub that save money, with the layover; "
    "offer it with its extra hours. Tell the user each leg is a separate ticket. Prices are the cheapest "
    "for the month unless the leg says exact_day: true."
)


class FlightArgs(BaseModel):
    destination: str = Field(description="City name in Russian or IATA code: 'Стамбул' or 'IST'.")
    month: int | None = Field(None, ge=1, le=12, description="Travel month; omit for the nearest dates.")
    origin: str | None = Field(None, description="Only for a leg that starts elsewhere: city name or IATA.")


class PlanArgs(BaseModel):
    stops: list[str] = Field(
        min_length=1,
        max_length=8,
        description="Cities to visit, in the user's order: ['Стамбул', 'Анталья'].",
    )
    order_fixed: bool = Field(
        True, description=f"False when we may choose the order (up to {MAX_OPEN_STOPS} stops)."
    )
    return_home: bool = Field(True, description="Fly back to the departure city at the end.")
    month: int | None = Field(None, ge=1, le=12, description="Travel month, when there is no date_from.")
    date_from: date | None = Field(None, description="Day the trip starts, if the user named one.")
    nights: list[int] | None = Field(
        None, max_length=8, description="Nights at each stop, in the order of `stops`; one number for all."
    )
    preference: Literal["cheapest", "balanced", "fastest"] = "balanced"
    origin: str | None = Field(None, description="Only when the trip starts away from the user's city.")

    @model_validator(mode="after")
    def _open_order_is_small(self):
        if not self.order_fixed and len(self.stops) > MAX_OPEN_STOPS:
            raise ValueError(f"the best order can be found for up to {MAX_OPEN_STOPS} stops")
        if self.nights and any(n < 0 or n > 60 for n in self.nights):
            raise ValueError("nights must be 0 to 60")
        return self


def plan_preview(result: dict) -> str:
    if result.get("error"):
        return result["error"]
    best = result["plans"][0]
    route = " → ".join([result["from"], *best["order"], *([result["from"]] if result["return_home"] else [])])
    total = best["total_price_rub"]
    return f"{route}: {'от ' + rub(total) if total else 'цен нет'}"


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

    catalog = load_catalog()

    async def plan_route(args: PlanArgs) -> dict:
        home_city = resolve(args.origin) if args.origin else city(current_origin.get())
        if home_city is None:
            return {"error": f"Unknown city: {args.origin!r}"}
        stops = [resolve_stop(name, catalog) for name in args.stops]
        unknown = [name for name, stop in zip(args.stops, stops, strict=True) if stop is None]
        if unknown:
            return {"error": f"Unknown city: {', '.join(unknown)}"}
        request = Request(
            home=Stop.of_city(home_city),
            stops=tuple(stops),
            order_fixed=args.order_fixed,
            return_home=args.return_home,
            month=args.month,
            date_from=args.date_from,
            nights=tuple(args.nights or ()),
            preference=args.preference,
        )
        plans = await plan(request, flights, network())
        notes = ["Каждый перелёт — отдельный билет в одну сторону: пересадки между ними на свой риск."]
        if args.date_from:
            notes.append("exact_day: false — цена самая низкая за месяц вылета у Aviasales, не на эту дату.")
        return {
            "from": home_city.name,
            "return_home": args.return_home,
            "order_was_chosen": not args.order_fixed and len(stops) > 1,
            "plans": [p.view() for p in plans],
            "notes": notes,
        }

    return [
        Tool(
            name="plan_route",
            title="Собираю маршрут",
            description=PLAN_DESCRIPTION,
            args=PlanArgs,
            handler=plan_route,
            preview=plan_preview,
        ),
        Tool(
            name="search_flights",
            title="Ищу билеты",
            description=DESCRIPTION,
            args=FlightArgs,
            handler=search_flights,
            preview=preview,
        ),
    ]
