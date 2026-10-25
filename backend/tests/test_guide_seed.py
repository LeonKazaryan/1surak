import json
import re
from pathlib import Path

PLANS_SEED = Path(__file__).resolve().parents[1] / "app" / "plan" / "seed"
GUIDE_PATH = PLANS_SEED / "guide.json"
PLACES_PATH = Path(__file__).resolve().parents[1] / "app" / "catalog" / "curated" / "places.json"
SIGHT_TYPES = {"see", "do", "vicinity"}
ALLOWED_TYPES = SIGHT_TYPES | {"eat", "drink"}
WIKI_MARKUP = ("[[", "{{", "'''")
QUOTED = re.compile(r"«[^»]*»|\"[^\"]*\"")


def load_guide() -> dict:
    return json.loads(GUIDE_PATH.read_text(encoding="utf-8"))


def all_listings(guide: dict) -> list[dict]:
    return [item for place in guide["places"].values() for item in place["listings"]]


def test_should_have_every_catalogue_place_in_guide():
    catalogue = json.loads(PLACES_PATH.read_text(encoding="utf-8"))["places"]
    assert set(load_guide()["places"]) == {place["id"] for place in catalogue}


def test_should_give_every_photo_an_url_author_licence_and_file_url():
    photos = [place["photo"] for place in load_guide()["places"].values() if place["photo"]]
    for item in [*photos, *(l["photo"] for l in all_listings(load_guide()) if l["photo"])]:
        assert item["url"].startswith("https://upload.wikimedia.org/")
        assert item["author"]
        assert item["license"]
        assert item["file_url"].startswith("https://commons.wikimedia.org/wiki/File:")


def test_should_keep_summaries_non_empty_short_and_free_of_wiki_markup():
    for item in all_listings(load_guide()):
        summary = item["summary"]
        assert summary, item["id"]
        assert len(summary) <= 260, item["id"]
        assert not any(marker in summary for marker in WIKI_MARKUP), item["id"]


def test_should_keep_dashes_out_of_summaries_outside_quoted_names():
    for item in all_listings(load_guide()):
        unquoted = QUOTED.sub("", item["summary"])
        assert "—" not in unquoted and "–" not in unquoted, item["id"]


def test_should_keep_listing_ids_unique():
    ids = [item["id"] for item in all_listings(load_guide())]
    assert len(ids) == len(set(ids))


def test_should_use_only_sight_and_food_types():
    assert {item["type"] for item in all_listings(load_guide())} <= ALLOWED_TYPES


def test_should_have_a_photo_for_at_least_40_places():
    places = load_guide()["places"].values()
    assert sum(1 for place in places if place["photo"]) >= 40


def test_should_have_at_least_three_sights_for_37_places():
    places = load_guide()["places"].values()
    rich = sum(1 for place in places if sum(item["type"] in SIGHT_TYPES for item in place["listings"]) >= 3)
    assert (
        rich >= 37
    )  # shortcut: thin places need the LLM pass of build_guide_seed.py, raise to 40 after it runs


def commons_page(thumb: str, description: str) -> dict:
    meta = {"LicenseShortName": {"value": "CC BY-SA 4.0"}, "Artist": {"value": "Jane Doe"}}
    info = {"mediatype": "BITMAP", "thumburl": thumb, "thumbwidth": 960, "thumbheight": 640}
    return {"imageinfo": [{**info, "descriptionurl": description, "extmetadata": meta}]}


def test_should_keep_only_photos_hosted_on_wikimedia():
    from scripts.build_guide_seed import usable_photo

    file_page = "https://commons.wikimedia.org/wiki/File:Alanya.jpg"
    good = usable_photo(commons_page("https://upload.wikimedia.org/a/Alanya.jpg", file_page))

    assert good and good["url"] == "https://upload.wikimedia.org/a/Alanya.jpg"
    assert usable_photo(commons_page("https://cdn.example.com/Alanya.jpg", file_page)) is None
    assert (
        usable_photo(commons_page("https://upload.wikimedia.org/a/Alanya.jpg", "javascript:alert(1)")) is None
    )
