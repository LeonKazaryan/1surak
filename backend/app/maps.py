"""Links to a place on Google Maps, where people check ratings, reviews and the way there.

No key and nothing stored: a Google listing keeps its own link, any other place is a search for its name on
the map around its point, close enough that the place itself is the first hit.
"""

from urllib.parse import quote

GOOGLE_MAPS = ("https://maps.google.com/", "https://www.google.com/maps")
ZOOM = 17  # a few streets: not another place of the same name across town


def google_maps_url(name: str, lat: float | None, lon: float | None, known: str | None = None) -> str | None:
    """Google's own link when `known` is one; a search for the name around the point; None without a point."""
    if known and known.startswith(GOOGLE_MAPS):
        return known
    if lat is None or lon is None or not name:
        return None
    return f"https://www.google.com/maps/search/{quote(name)}/@{lat},{lon},{ZOOM}z"
