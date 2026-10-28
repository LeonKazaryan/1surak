"""Whether a saved trip still holds: its tickets go stale in a day, and a month that is over can't be booked."""

from datetime import datetime, timedelta

from app.flights import city
from app.flights.client import departure_month
from app.trip.brief import TripBrief, chips
from app.trip.passport import passport

STALE_AFTER = timedelta(hours=24)


def dates_passed(brief: TripBrief, now: datetime) -> bool:
    today = now.date()
    if brief.date_from:
        return brief.date_from < today
    if brief.month and brief.priced_at:
        # «ноябрь» meant the November coming when the prices were found
        return departure_month(brief.month, brief.priced_at.date()) < f"{today.year}-{today.month:02d}"
    return False


def trip_status(brief: TripBrief, now: datetime) -> dict:
    origin = city(brief.priced_from)
    return {
        "summary": chips(brief),
        "passport": passport(brief),
        "departure": origin.from_text if origin else None,
        "priced_at": brief.priced_at.isoformat() if brief.priced_at else None,
        "stale": brief.priced_at is not None and now - brief.priced_at > STALE_AFTER,
        "dates_passed": dates_passed(brief, now),
        "nudge": brief.nudge,  # a quick reply from the traveller's earlier trips, under this turn's cards
    }
