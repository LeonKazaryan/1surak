"""Fresh tickets for the cards a trip already shows: the same places and words, new prices, no model call."""

from app.catalog.search import Snapshot, card, with_flights
from app.flights import Flights, city
from app.trip.brief import TripBrief
from app.trip.routes import rebuild_route, route_card


async def _fresh(
    old: dict, brief: TripBrief, snapshots: dict[str, Snapshot], flights: Flights
) -> dict | None:
    if old.get("type") == "route":
        stops = [snapshots.get(s["id"]) for s in old["stops"]]
        if None in stops:
            return None
        nights = sum(s["nights"] for s in old["stops"])  # as shown, even if the brief changed since
        plan = await rebuild_route(stops, brief, flights, city(brief.priced_from), nights)
        return route_card(plan, brief.month, old.get("why", ""), old.get("tradeoff"))
    snapshot = snapshots.get(old["id"])
    if snapshot is None:
        return None
    view = card(snapshot, brief.month)
    return {"type": "place", **view, "why": old.get("why", ""), "tradeoff": old.get("tradeoff")}


def _price(view: dict) -> int | None:
    if view.get("type") == "route":
        return view.get("total_rub")
    return (view.get("flight") or {}).get("price_rub")


async def reprice(
    cards: list[dict], brief: TripBrief, snapshots: dict[str, Snapshot], flights: Flights
) -> list[dict]:
    """Empty when the cards are gone from the catalogue, or had tickets and Aviasales has none now."""
    places = [snapshots[c["id"]] for c in cards if c.get("type") != "route" and c["id"] in snapshots]
    await with_flights(places, flights, brief.priced_from, brief.month)
    result = []
    for old in cards:
        new = await _fresh(old, brief, snapshots, flights)
        if new is None:
            continue
        before, after = _price(old), _price(new)
        if before and after:
            new["price_change"] = {"rub": after - before, "since": brief.priced_at.isoformat()}
        result.append(new)
    if any(_price(c) for c in cards) and not any(_price(c) for c in result):
        return []
    return result
