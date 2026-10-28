from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.catalog.catalog import load_catalog
from app.flights import Flights, city, current_origin, network
from app.flights.client import search_link
from app.flights.dictionary import find_city
from app.flights.planner import MAX_OPEN_STOPS, Request, Stop, plan, plan_card, resolve_stop
from app.money import current_currency, money
from app.tools.registry import Tool, ToolReply

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
    return f"{route}: {'от ' + best['total'] if best['total'] else 'цен нет'}"


def resolve(name: str | None):
    return find_city(name)


def flight_tools(flights: Flights) -> list[Tool]:
    async def search_flights(args: FlightArgs) -> dict:
        origin = resolve(args.origin) if args.origin else city(current_origin.get())
        destination = resolve(args.destination)
        if origin is None or destination is None:
            return {"error": f"Unknown city: {args.origin if origin is None else args.destination!r}"}
        found = await flights.route(origin.code, destination.code, args.month)
        result = {"from": origin.name, "to": destination.name}
        if found:
            return {**result, "tickets": found.view()}
        # the cache has no fare for the month: the nearest dates as a guide, and the live search for the month
        near = await flights.route(origin.code, destination.code) if args.month else None
        result |= {"tickets": None, "search_link": search_link(origin.code, destination.code, args.month)}
        if near:
            note = (
                "No fare cached for these dates: `guide` is the cheapest of the nearest dates, a price guide."
            )
            return {**result, "guide": near.view(), "note": note}
        return {**result, "note": "No fare cached yet: the live search on Aviasales has the day's fares."}

    def preview(result: dict) -> str:
        if result.get("error"):
            return result["error"]
        ticket = result.get("tickets")
        if not ticket and result.get("guide"):
            return f"{result['from']} → {result['to']}: ориентир от {money(result['guide']['price_rub'])} по ближайшим датам"
        if not ticket:
            return f"{result['from']} → {result['to']}: цены в живом поиске Aviasales"
        stops = "прямой" if ticket["transfers"] == 0 else f"пересадок: {ticket['transfers']}"
        return f"{result['from']} → {result['to']}: от {money(ticket['price_rub'])}, {stops}"

    catalog = load_catalog()

    async def plan_route(args: PlanArgs) -> dict | ToolReply:
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
        elif plans and not plans[0].dates_chained:
            notes.append(
                "dates_chained: false — самые дешёвые даты не стыкуются, точные даты подберём при покупке."
            )
        views = []
        for p in plans:
            view = p.view()
            # the model quotes prices as given: in the user's currency, not raw roubles
            view["total"] = money(view.pop("total_price_rub")) if view["total_price_rub"] else None
            if with_hubs := view.pop("total_with_connections_rub", None):
                view["total_with_connections"] = money(with_hubs)
            # the id build_trip takes to make it a whole trip: hotels, days, the bill
            places = [catalog.find(s.name) for s in p.stops]
            if all(places):
                view["trip_id"] = "+".join(place.id for place in places)
            views.append(view)
        result = {
            "from": home_city.name,
            "return_home": args.return_home,
            "order_was_chosen": not args.order_fixed and len(stops) > 1,
            "plans": views,
            "notes": notes,
            "next": "The route is on screen as a card with prices and buy links. Answer now in 2-4 sentences: "
            "the best order, the total, the dates, cheaper_via if any; do not list every ticket. When the user "
            "asks for the whole trip (hotels, days, the bill), call build_trip with the chosen plan's trip_id, "
            "then show_trip.",
        }
        if not plans:
            return result
        home = Stop.of_city(home_city)
        event = {
            "type": "flight_plan",
            "from": home_city.name,
            "plans": [plan_card(p, home, args.return_home, best=i == 0) for i, p in enumerate(plans)],
            "currency": current_currency.get().view(),
        }
        return ToolReply(result=result, event=event)

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
