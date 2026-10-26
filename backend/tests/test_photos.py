"""Photos found live for places the guide has none for: by Wikidata id or by name near the coordinates."""

import asyncio

import httpx

from app.catalog.catalog import load_catalog
from app.catalog.search import build_snapshot, card
from app.destinations import discovered_place
from app.photos import PhotoFinder

COMMONS = {
    "query": {
        "pages": [
            {
                "imageinfo": [
                    {
                        "thumburl": "https://upload.wikimedia.org/izmir.jpg?utm_source=x",
                        "thumbwidth": 1280,
                        "thumbheight": 820,
                        "descriptionurl": "https://commons.wikimedia.org/wiki/File:Izmir.jpg",
                        "extmetadata": {
                            "Artist": {"value": '<a href="https://x">Rafaela Ely</a>'},
                            "LicenseShortName": {"value": "CC BY 2.0"},
                        },
                    }
                ]
            }
        ]
    }
}


def finder(article: dict, p18: str | None, seen: list[str] | None = None) -> PhotoFinder:
    def answer(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request.url.host)
        if request.url.host == "ru.wikipedia.org":
            return httpx.Response(200, json=article)
        if request.url.host == "www.wikidata.org":
            claims = {"P18": [{"mainsnak": {"datavalue": {"value": p18}}}]} if p18 else {}
            return httpx.Response(200, json={"claims": claims})
        return httpx.Response(200, json=COMMONS)

    return PhotoFinder(httpx.AsyncClient(transport=httpx.MockTransport(answer)))


def page(title: str, lat: float, lon: float, image: str, qid: str = "Q35997", index: int = 1) -> dict:
    return {
        "title": title,
        "index": index,
        "coordinates": [{"lat": lat, "lon": lon}],
        "pageimage": image,
        "pageprops": {"wikibase_item": qid},
    }


def test_should_find_a_route_map_city_photo_by_name_near_its_coordinates():
    izmir = discovered_place("IZM")
    far = page("Измир (значения)", 0.0, 0.0, "Far.jpg", "Q1", index=1)
    near = page("Измир", izmir.lat, izmir.lon, "Izmir-montage.jpg", index=2)

    photo = asyncio.run(finder({"query": {"pages": [far, near]}}, "Izmir.jpg").find(izmir))

    assert photo == {
        "url": "https://upload.wikimedia.org/izmir.jpg",
        "width": 1280,
        "height": 820,
        "author": "Rafaela Ely",
        "license": "CC BY 2.0",
        "file_url": "https://commons.wikimedia.org/wiki/File:Izmir.jpg",
    }


def test_should_never_take_a_map_or_a_flag_for_a_photo():
    izmir = discovered_place("IZM")
    only_map = page("Измир", izmir.lat, izmir.lon, "Map_of_Izmir_ru.svg")

    assert asyncio.run(finder({"query": {"pages": [only_map]}}, "Flag of Izmir.png").find(izmir)) is None


def test_should_skip_the_search_for_a_catalogue_place_with_a_wikidata_id():
    goa = load_catalog().find("goa")
    seen: list[str] = []

    photo = asyncio.run(finder({}, "Calangute.jpg", seen).find(goa))

    assert photo is not None and "ru.wikipedia.org" not in seen


def test_should_not_put_made_up_estimates_on_a_route_map_city_card():
    izmir = discovered_place("IZM")
    view = card(build_snapshot(izmir, {}, {}, {}))

    assert "verified" not in view and view["watch_out"] == []  # no «not checked» badge or note
    assert (view["price_level"], view["price"], view["kids"], view["kids_fit"]) == (None, None, None, None)
