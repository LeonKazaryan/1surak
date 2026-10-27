"""A guide for any city from Wikidata and OpenStreetMap, and days that keep to one part of town."""

import asyncio
import json
from datetime import date, datetime
from types import SimpleNamespace

import httpx

from app.catalog.catalog import load_catalog
from app.plan.guide import Guide, Spot
from app.plan.hotels import Party
from app.plan.itinerary import Stay, plan_days
from app.plan.live_guide import LiveGuides, cuisine_ru, cuisine_tags, food_from, kind_of, merged, sights_from

CATALOG = load_catalog()


def row(
    qid: str, name: str, links: int, types: str, lat: float, lon: float, about: str = "", image: str = ""
) -> dict:
    found = {
        "item": {"value": f"http://www.wikidata.org/entity/{qid}"},
        "links": {"value": str(links)},
        "name": {"value": name},
        "types": {"value": types},
        "at": {"value": f"Point({lon} {lat})"},
    }
    if about:
        found["about"] = {"value": about}
    if image:
        found["image"] = {"value": f"http://commons.wikimedia.org/wiki/Special:FilePath/{image}"}
    return found


ROWS = [
    row("Q60", "Нью-Йорк", 325, "big city|metropolis", 40.71, -74.0),
    row(
        "Q9188",
        "Эмпайр-стейт-билдинг",
        125,
        "office building|skyscraper",
        40.748,
        -73.985,
        "небоскрёб",
        "Empire%20State%20Building.jpg",
    ),
    row("Q11285", "Трамп-тауэр", 47, "skyscraper", 40.762, -73.973),
    row(
        "Q160236", "Метрополитен-музей", 88, "production company|art museum|museum", 40.779, -73.963, "музей"
    ),
    row("Q11299", "Бродвейский театр", 64, "theatrical genre", 40.759, -73.985),
    row("Q1028137", "Новый Амстердам", 45, "former settlement|fortified town", 40.704, -74.013),
    row("Q11297", "Гринвич-Виллидж", 52, "neighborhood of Manhattan|NRHP district", 40.733, -74.003, "район"),
    row("Q1194", "Nasdaq", 92, "organization|stock exchange", 40.757, -73.986),
]


def test_should_link_every_place_with_a_point_to_google_maps():
    osm = Spot(
        "osm-n1",
        "eat",
        "Der Garten",
        "",
        lat=48.2,
        lon=16.36,
        source_url="https://www.openstreetmap.org/node/1",
    )
    google = Spot(
        "gp-1", "eat", "Sultans", "", lat=48.2, lon=16.37, source_url="https://maps.google.com/?cid=42"
    )

    # a search for the name around its point: the place itself, not one of the same name across town
    assert osm.view()["maps_url"] == "https://www.google.com/maps/search/Der%20Garten/@48.2,16.36,17z"
    assert google.view()["maps_url"] == "https://maps.google.com/?cid=42"  # Google's own listing
    assert Spot("x", "see", "Нигде", "").maps_url is None  # no point, no guess


def test_should_sort_wikidata_places_into_sights_and_walks():
    assert kind_of("art museum|production company", 88) == "see"
    assert kind_of("skyscraper", 125) == "see" and kind_of("skyscraper", 47) is None  # iconic only
    assert kind_of("theatrical genre", 64) is None and kind_of("former settlement|fortified town", 45) is None
    assert (
        kind_of("neighborhood of Manhattan", 52) == "walk"
        and kind_of("organization|stock exchange", 92) is None
    )

    sights, walks, files = sights_from(ROWS, "city-nyc")

    assert [s["name"] for s in sights] == ["Эмпайр-стейт-билдинг", "Метрополитен-музей"]
    assert [w["name"] for w in walks] == ["Гринвич-Виллидж"]
    assert (
        sights[0]["summary"] == "Небоскрёб"
        and sights[0]["star"]
        and files == {"city-nyc-wd-q9188": "Empire State Building.jpg"}
    )


def nominatim(name: str, cuisine: str | None, lat: float, **tags) -> dict:
    extratags = {"cuisine": cuisine, **tags} if cuisine else tags
    return {
        "name": name,
        "lat": str(lat),
        "lon": "-73.99",
        "osm_type": "node",
        "osm_id": hash(name) % 10**6,
        "type": "restaurant",
        "extratags": extratags,
    }


def test_should_pick_varied_restaurants_and_never_guess_a_cuisine():
    found = food_from(
        [
            nominatim("Pizza A", "pizza", 40.75),
            nominatim("Pizza B", "pizza", 40.751),
            nominatim("Pizza C", "pizza", 40.752),
            nominatim("Famous Deli", "deli", 40.76, wikidata="Q1"),
            nominatim("Corner Spot", None, 40.753),
        ],
        (40.75, -73.99),
    )

    names = [f["name"] for f in found]
    assert names[0] == "Famous Deli" and "Pizza C" not in names  # the notable first, a cuisine at most twice
    assert next(f for f in found if f["name"] == "Corner Spot")["summary"] == "Ресторан"


def test_should_say_a_cuisine_in_two_russian_words_at_most():
    tags = cuisine_tags("burger;regional;barbecue;grill")

    assert tags == ["burger", "regional"]  # a short line, not the whole tag list
    assert cuisine_ru(tags) == "Бургеры, местная кухня"
    assert cuisine_ru(cuisine_tags("levantine")) == "Ближневосточная кухня"
    assert cuisine_ru(cuisine_tags("jewish;deli")) is None  # a rare one goes to the model, never shown raw


def test_should_find_a_guide_for_any_city_and_keep_the_seed_first():
    def handler(request: httpx.Request) -> httpx.Response:
        if "sparql" in str(request.url):
            return httpx.Response(200, json={"results": {"bindings": ROWS}})
        if "nominatim" in str(request.url):
            return httpx.Response(200, json=[nominatim("Katz's", "jewish;deli", 40.722)])
        pages = {
            "1": {
                "title": "File:Empire State Building.jpg",
                "imageinfo": [
                    {
                        "thumburl": "https://upload.wikimedia.org/esb.jpg",
                        "descriptionurl": "https://commons.wikimedia.org/wiki/File:ESB.jpg",
                        "extmetadata": {
                            "Artist": {"value": "<b>Jane</b>"},
                            "LicenseShortName": {"value": "CC BY 4.0"},
                        },
                    }
                ],
            }
        }
        return httpx.Response(200, json={"query": {"pages": pages}})

    async def create(**kwargs):
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=json.dumps({"notes": ["еврейская кухня, деликатесы"]}))
                )
            ]
        )

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    guides = LiveGuides(None, CATALOG.find, client, "m", transport=httpx.MockTransport(handler))

    guide = asyncio.run(guides.guide(CATALOG.find("city-nyc"), wait_s=None))

    assert [s.name for s in guide.sights] == ["Эмпайр-стейт-билдинг", "Метрополитен-музей", "Гринвич-Виллидж"]
    assert guide.sights[0].photo.author == "Jane" and guide.sights[0].photo.license == "CC BY 4.0"
    assert [(f.name, f.summary) for f in guide.food] == [("Katz's", "Еврейская кухня, деликатесы")]


def spot(id: str, lat: float, lon: float, type: str = "see", name: str | None = None) -> Spot:
    return Spot(id=id, type=type, name=name or id, summary="", lat=lat, lon=lon)


def test_should_keep_each_day_in_one_part_of_town_and_walk_the_neighbourhoods_after():
    uptown = [spot("met", 40.779, -73.963), spot("guggenheim", 40.783, -73.959)]
    downtown = [spot("memorial", 40.711, -74.013), spot("wtc", 40.713, -74.013)]
    guide = Guide(
        "city-nyc",
        sights=(uptown[0], downtown[0], uptown[1], downtown[1], spot("soho", 40.723, -74.0, "walk", "Сохо")),
        food=(spot("uptown-deli", 40.78, -73.96, "eat"), spot("downtown-deli", 40.712, -74.012, "eat")),
    )
    stay = Stay(
        guide,
        date(2027, 5, 15),
        date(2027, 5, 19),
        datetime(2027, 5, 15, 23),
        datetime(2027, 5, 19, 9),
        (40.756, -73.986),
    )

    days = plan_days(stay, Party(adults=2))

    sights = [[i.spot.id for i in d.items if i.kind == "sight"] for d in days]
    assert ["met", "guggenheim"] in sights and ["memorial", "wtc"] in sights  # never Met and WTC in one day
    lunch = next(i for d in days for i in d.items if i.title.startswith("Обед"))
    assert lunch.spot.id in ("uptown-deli", "downtown-deli")
    assert any(i.kind == "walk" and i.title == "Прогулка: Сохо" for d in days for i in d.items)


def test_should_add_the_live_spots_after_the_seeds_own():
    seed = Guide("x", sights=(spot("a", 1, 1, name="Музей"),), food=())
    live = Guide(
        "x",
        sights=(spot("b", 1, 1, name="Музей"), spot("c", 2, 2, name="Парк")),
        food=(spot("d", 1, 1, "eat"),),
    )

    both = merged(seed, live)

    assert [s.id for s in both.sights] == ["a", "c"] and [f.id for f in both.food] == ["d"]
