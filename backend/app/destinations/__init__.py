"""Destinations beyond the catalogue: every city the route map flies to from the user's city.

The catalogue's 53 places are hand-checked. A city from the route map becomes a Place too, with what we can
get for it and nothing more: its name, country, coordinates and airport from Travelpayouts; its climate and
sea from Open-Meteo (one year, fetched once and kept in the facts table, see climate.py); its kind of trip
from those facts (a coast with sea data is «sea», a high town «mountains»). Its visa rule is the catalogue's
when we curate that country, otherwise «not checked». Every such place says `verified=False`, and its cards
say so.
"""

from collections.abc import Iterable
from datetime import datetime
from functools import cache

from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.catalog import Catalog, Country, Place, load_catalog
from app.catalog.search import Snapshot, build_snapshot, load_snapshots
from app.facts.service import resolve_entities
from app.flights import city, city_code
from app.flights.network import Network

PREFIX = "city-"
UNVERIFIED = "Не из нашего каталога: визу, цены и отдых команда не проверяла, климат по данным 2025 года"
UNKNOWN_VISA_NOTE = "Визовый режим для этой страны мы не проверяли: уточним перед поездкой"
MOUNTAIN_M = 900  # a town this high is a mountain trip
WARM_SEA_C = 20  # a coast whose sea gets this warm in some month is a sea trip
DEFAULT_LEVEL = 2
MAX_CANDIDATES = 120  # the nearest direct destinations a search looks at


def place_id(code: str) -> str:
    return f"{PREFIX}{code.lower()}"


def qid(code: str) -> str:
    return f"iata:{code}"


@cache
def catalog_cities() -> frozenset[str]:
    """The cities the catalogue already covers: those stay the catalogue's, with their checked facts."""
    return frozenset(city_code(p.airport) for p in load_catalog().places if p.airport)


@cache
def _levels() -> dict[str, int]:
    """A country's price level: the median of its catalogue places, when we have some."""
    by_country: dict[str, list[int]] = {}
    for p in load_catalog().places:
        by_country.setdefault(p.country.code, []).append(p.price_level)
    return {code: sorted(levels)[len(levels) // 2] for code, levels in by_country.items()}


def kinds_from(facts: dict) -> tuple[str, ...]:
    """The trips a city suits, from its facts: always a city break; sea or mountains when the data says so."""
    kinds = ["city"]
    sea = [v for k, v in facts.items() if k.startswith("sea_temp")]
    if facts.get("coastal") and sea and max(sea) >= WARM_SEA_C:
        kinds.insert(0, "sea")
    if (facts.get("elevation") or 0) >= MOUNTAIN_M:
        kinds.append("mountains")
    return tuple(kinds)


_kinds: dict[str, tuple[str, ...]] = {}  # learnt from the facts as places are loaded, by city code


def discovered_place(code: str) -> Place | None:
    """A route-map city as a Place; None for the catalogue's own cities and cities we cannot place."""
    c = city(code)
    if c is None or not c.country_code or not c.tz or c.code in catalog_cities():
        return None
    catalog = load_catalog()
    country = catalog.countries.get(c.country_code) or Country(
        c.country_code, c.country, "unknown", None, UNKNOWN_VISA_NOTE
    )
    return Place(
        id=place_id(c.code),
        qid=qid(c.code),
        name=c.name,
        country=country,
        kinds=_kinds.get(c.code, ("city",)),
        airport=c.code,
        lat=c.lat,
        lon=c.lon,
        price_level=_levels().get(c.country_code, DEFAULT_LEVEL),
        kids="ok",
        highlights=(),
        watch_out=(UNVERIFIED,),
        train_min=None,
        verified=False,
    )


def find(key: str) -> Place | None:
    """By our id («city-tas») or by the city's name or code, for a city the catalogue does not have."""
    needle = key.strip()
    if needle.casefold().startswith(PREFIX):
        return discovered_place(needle[len(PREFIX) :].upper())
    from app.flights.dictionary import find_city

    found = find_city(needle)
    return discovered_place(found.code) if found else None


def candidates(live: list[str], network: Network, origin: str, limit: int = MAX_CANDIDATES) -> list[str]:
    """Live destinations first (where people fly now, with a change or not), then the route map's direct ones;
    only cities the catalogue does not cover and that we can place."""
    home = city_code(origin)
    merged = dict.fromkeys([*live, *reachable(network, origin, limit=10_000)])
    return [c for c in merged if c != home and c not in catalog_cities() and discovered_place(c)][:limit]


NAMED_COUNTRIES = 5  # a search naming this few countries looks at their main cities, wherever they are
CITIES_PER_COUNTRY = 3


def country_cities(
    names: list[str] | None, network: Network, per_country: int = CITIES_PER_COUNTRY
) -> list[str]:
    """The main cities of the countries the user named, whether or not anyone flies there from home:
    «хочу в Эфиопию» from Astana is Addis Ababa with a change. The best connected airports come first."""
    if not names or len(names) > NAMED_COUNTRIES:
        return []
    from app.flights.dictionary import cities

    wanted = {n.casefold() for n in names}
    by_country: dict[str, list[tuple[int, str]]] = {}
    for c in cities().values():
        if c.country.casefold() in wanted or (c.country_code and _catalog_name(c.country_code) in wanted):
            by_country.setdefault(c.country_code or c.country, []).append(
                (len(network.links_from(c.code)), c.code)
            )
    found = []
    for ranked in by_country.values():
        found += [code for links, code in sorted(ranked, reverse=True)[:per_country] if links]
    return found


def _catalog_name(code: str) -> str | None:
    country = load_catalog().countries.get(code)
    return country.name.casefold() if country else None


def in_countries(codes: list[str], names: list[str] | None) -> list[str]:
    """The cities in the countries the search is limited to; all of them without a limit."""
    if not names:
        return codes
    wanted = {n.casefold() for n in names}
    return [c for c in codes if (p := discovered_place(c)) and p.country.name.casefold() in wanted]


def reachable(network: Network, origin: str, limit: int = MAX_CANDIDATES) -> list[str]:
    """Cities with a direct flight from the origin that the catalogue does not cover, nearest first."""
    home = city_code(origin)
    return [
        link.destination.code
        for link in network.links_from(home)
        if link.destination.code not in catalog_cities() and link.destination.code != home
    ][:limit]


async def load_discovered(
    db: AsyncSession, codes: Iterable[str], now: datetime, need_climate: bool = True
) -> list[Snapshot]:
    """Snapshots of route-map cities. For a search only those with their climate in the facts table;
    a city the user named (need_climate=False) comes even without it, with no climate to show."""
    codes = [c for c in dict.fromkeys(codes) if city(c)]
    facts = await resolve_entities(db, "place", [qid(c) for c in codes], now)
    known = sorted({cc for c in codes if (cc := city(c).country_code) in load_catalog().countries})
    countries = await resolve_entities(db, "country", known, now) if known else {}
    snapshots = []
    for code in codes:
        resolved = facts[qid(code)]
        if need_climate and not any(attribute == "air_max" for attribute, _ in resolved):
            continue  # no climate yet: the fetcher brings it, and the next search includes it
        plain = {f"{a}{p or ''}": r.chosen.value for (a, p), r in resolved.items()}
        _kinds[code] = kinds_from(plain)
        place = discovered_place(code)
        if place is not None:
            snapshots.append(build_snapshot(place, resolved, {}, countries.get(place.country.code, {})))
    return snapshots


async def snapshots_by_id(db: AsyncSession, catalog: Catalog, now: datetime, ids: Iterable[str] = ()) -> dict:
    """Snapshots by place id: the catalogue's, plus the route-map cities among `ids` (cards, build_trip)."""
    found = {s.place.id: s for s in await load_snapshots(db, catalog, now)}
    codes = [i[len(PREFIX) :].upper() for i in ids if i.startswith(PREFIX) and i not in found]
    if codes:
        found.update({s.place.id: s for s in await load_discovered(db, codes, now, need_climate=False)})
    return found
