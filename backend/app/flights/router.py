from fastapi import APIRouter, Query

from app.flights.dictionary import nearest

router = APIRouter(prefix="/api/places", tags=["Places"])


@router.get("/nearby")
async def nearby(
    lat: float = Query(ge=-90, le=90), lon: float = Query(ge=-180, le=180), limit: int = 8
) -> dict:
    """Cities with an airport nearest to a point: the departure suggestions before the user types."""
    return {"items": [c.view() for c in nearest(lat, lon, min(max(limit, 1), 20))]}
