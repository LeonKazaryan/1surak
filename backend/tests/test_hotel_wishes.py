"""Real hotels around any place (seed + OpenStreetMap) and the guest's wishes checked against real sources."""

import asyncio
import json
from dataclasses import replace
from datetime import UTC, date, datetime
from types import SimpleNamespace

import httpx
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.catalog.catalog import load_catalog
from app.db import init_db
from app.hotels import HotelSource, Listed, Offer, evidence, real_hotel
from app.hotels.evidence import Evidence, EvidenceFinder, Source, WishJudge, hotel_wishes
from app.hotels.osm import OsmHotels, merge_listings, osm_listed
from app.kb.page import Page
from app.kb.web import WebResult, excluded
from app.plan.hotels import Party, Wishes, choose_hotel
from app.plan.tools import plan_tools
from app.tools import ToolRegistry
from app.trip import TripState
from tests.conftest import fresh_database
from tests.test_plan_tools import COUPLE, TICKETS, call, sessionmaker  # noqa: F401  (the fixture)

CATALOG = load_catalog()
SOCHI = CATALOG.find("sochi")
NOW = datetime(2026, 10, 26, 12, tzinfo=UTC)

NOMINATIM = [
    {
        "osm_type": "node",
        "osm_id": 11,
        "lat": "43.5757",
        "lon": "39.7269",
        "category": "tourism",
        "type": "hotel",
        "name": "Hyatt Regency Sochi",
        "extratags": {"stars": "5", "internet_access": "wlan", "website": "https://hyatt.com/sochi"},
    },
    {
        "osm_type": "way",
        "osm_id": 22,
        "lat": "43.59",
        "lon": "39.73",
        "category": "tourism",
        "type": "hotel",
        "name": "City Park Hotel",
        "extratags": {"stars": "4S", "contact:website": "www.cph-sochi.com", "building": "yes"},
    },
    {
        "osm_type": "node",
        "osm_id": 33,
        "lat": "43.58",
        "lon": "39.72",
        "category": "amenity",
        "type": "cafe",
        "name": "Кафе",
    },
    {
        "osm_type": "node",
        "osm_id": 44,
        "lat": "43.58",
        "lon": "39.72",
        "category": "tourism",
        "type": "hotel",
        "name": "",
    },
]


def maker_for(suffix: str):
    url = fresh_database(suffix)

    async def setup():
        engine = create_async_engine(url, poolclass=NullPool)
        await init_db(engine)
        return engine, async_sessionmaker(engine, expire_on_commit=False)

    return asyncio.run(setup())


def listed(i: int, name: str, stars: int | None = 4, website: str | None = None, tags=None) -> Listed:
    return Listed(
        f"sochi-hq{i}",
        "sochi",
        name,
        stars,
        43.58,
        39.72,
        500,
        None,
        f"https://www.wikidata.org/wiki/Q{i}",
        website,
        tags or {},
    )


def hotel(i: int, name: str = "", stars: int | None = 4, website: str | None = None, tags=None, evidence=()):
    row = listed(i, name or f"Отель {i}", stars, website, tags)
    return replace(real_hotel(row, [Offer(row.id, "breakfast", 6000 + 100 * i)]), evidence=evidence)


class FakeSearch:
    def __init__(self, results: list[WebResult] | None = None, delay: float = 0.0):
        self.results = results or []
        self.delay = delay
        self.queries: list[str] = []

    async def search(self, query: str) -> list[WebResult]:
        self.queries.append(query)
        await asyncio.sleep(self.delay)
        return self.results


class FakeReader:
    def __init__(self, text: str):
        self.text = text
        self.urls: list[str] = []

    async def read(self, url: str) -> Page:
        self.urls.append(url)
        return Page(url=url, title="Отель", text=self.text)


class FakeClient:
    """The judge's model: answers every hotel with the same verdicts and remembers what it was shown."""

    def __init__(self, wishes: list[dict]):
        self.answer = {"wishes": wishes}
        self.prompts: list[str] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    async def create(self, **kwargs):
        self.prompts.append(kwargs["messages"][-1]["content"])
        self.schema = kwargs["response_format"]["json_schema"]["schema"]
        message = SimpleNamespace(content=json.dumps(self.answer, ensure_ascii=False))
        return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=None)


def finder(maker, client, search=None, reader=None, budget_s: float = 5.0) -> EvidenceFinder:
    return EvidenceFinder(
        maker,
        WishJudge(client, "test-model"),
        search=search,
        reader=reader,
        clock=lambda: NOW,
        budget_s=budget_s,
    )


def test_should_pick_the_wishes_about_the_hotel_out_of_all_wishes():
    wishes = [
        "с видом на море",
        "без пересадок",
        "можно с собакой",
        "ванна в номере",
        "хороший wi-fi",
        "отель до 8 000 ₽ за ночь",
    ]

    assert hotel_wishes(wishes) == ["с видом на море", "можно с собакой", "ванна в номере", "хороший wi-fi"]
    assert hotel_wishes(None) == []


def test_should_skip_tripadvisor_and_booking_on_every_domain():
    assert excluded("https://www.tripadvisor.co.uk/Hotel_Review-x")
    assert excluded("https://www.booking.com/hotel/ru/x.html")
    assert excluded("https://www.zenhotels.com/hotel/en-us/russia/sochi/x")  # Ostrovok's own brand: rule 6.6
    assert excluded("https://www.readytotrip.ru/hotels/turkey/antalya/kaleici/tuvana-hotel")
    assert excluded("https://www.hotelscombined.com.sg/Hotel/Tuvana_Hotel.htm")
    assert excluded("https://www.momondo.co.za/hotels/antalya/Tuvana-Hotel")
    assert not excluded("https://otzovik.com/reviews/hotel_x")


def test_should_read_osm_hotels_with_their_stars_site_and_amenity_tags():
    hyatt, park = osm_listed(NOMINATIM, SOCHI)

    assert (hyatt.id, hyatt.name, hyatt.stars, hyatt.website) == (
        "sochi-hon11",
        "Hyatt Regency Sochi",
        5,
        "https://hyatt.com/sochi",
    )
    assert (
        hyatt.tags == {"internet_access": "wlan"}
        and hyatt.source_url == "https://www.openstreetmap.org/node/11"
    )
    assert (park.id, park.stars, park.website, park.tags) == (
        "sochi-how22",
        4,
        "https://www.cph-sochi.com",
        {},
    )
    assert hyatt.centre_m < 2000
    twice = [*NOMINATIM, {**NOMINATIM[0], "osm_type": "way", "osm_id": 55, "lat": "43.5759"}]
    assert [h.id for h in osm_listed(twice, SOCHI)] == [
        "sochi-hon11",
        "sochi-how22",
    ]  # a point and its building


def test_should_merge_osm_into_the_directory_without_doubles():
    photo = {"url": "https://upload.wikimedia.org/x.jpg", "author": "A", "license": "CC0"}
    seed = (replace(listed(1, "Hyatt Regency Sochi", stars=None), photo=photo),)

    merged = merge_listings(seed, osm_listed(NOMINATIM, SOCHI))

    assert [h.id for h in merged] == ["sochi-hq1", "sochi-how22"]
    hyatt = merged[0]
    assert (hyatt.stars, hyatt.website, hyatt.tags, hyatt.photo) == (
        5,
        "https://hyatt.com/sochi",
        {"internet_access": "wlan"},
        photo,
    )


def test_should_fetch_osm_hotels_once_and_keep_them():
    engine, maker = maker_for("osm")
    requests: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=NOMINATIM)

    def broken(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    async def scenario():
        failed = await OsmHotels(maker, transport=httpx.MockTransport(broken)).around(SOCHI)
        first = await OsmHotels(maker, transport=httpx.MockTransport(answer)).around(SOCHI)
        again = await OsmHotels(maker, transport=httpx.MockTransport(answer)).around(SOCHI)
        return failed, first, again

    try:
        failed, first, again = asyncio.run(scenario())
    finally:
        asyncio.run(engine.dispose())

    assert failed == []  # a failure is not remembered: the next search asks again
    assert [h.name for h in first] == ["Hyatt Regency Sochi", "City Park Hotel"] and again == first
    assert len(requests) == 1
    params = requests[0].url.params
    assert params["q"] == "hotel" and params["bounded"] == "1" and params["extratags"] == "1"
    assert "1surak" in requests[0].headers["user-agent"]


SEA = "с видом на море"
BATH = "с ванной"
DOG = "можно с собакой"


def test_should_confirm_a_wish_only_with_a_quote_that_is_really_in_a_source():
    engine, maker = maker_for("wishes")
    search = FakeSearch(
        [
            WebResult(
                "https://otzovik.com/reviews/hyatt", "Отзыв", "Потрясающий вид на море открывается с балкона."
            ),
            WebResult("https://www.booking.com/hotel/ru/hyatt.html", "Booking", "Pets are allowed."),
            WebResult("https://www.tripadvisor.co.uk/Hotel_Review-1", "TA", "Bathtub in every room."),
        ]
    )
    client = FakeClient(
        [
            {
                "wish": SEA,
                "verdict": "yes",
                "quote": "Потрясающий вид на море открывается с балкона",
                "source": 1,
                "note": None,
            },
            {
                "wish": BATH,
                "verdict": "yes",
                "quote": "В каждом номере глубокая ванна",
                "source": 1,
                "note": None,
            },
        ]
    )
    hyatt = hotel(1, "Hyatt Regency Sochi")
    try:
        found = asyncio.run(finder(maker, client, search).check(SOCHI, [hyatt], [SEA, BATH]))
    finally:
        asyncio.run(engine.dispose())

    assert found[hyatt.id] == (
        Evidence(
            SEA,
            "yes",
            "Потрясающий вид на море открывается с балкона",
            None,
            "otzovik.com",
            "https://otzovik.com/reviews/hyatt",
        ),
        Evidence(BATH, "unknown"),  # the model made the quote up: not on any page, so not a confirmation
    )
    assert "Hyatt Regency Sochi" in search.queries[0] and "Сочи" in search.queries[0]
    shown = client.prompts[0]
    assert "otzovik.com" in shown and "booking" not in shown and "tripadvisor" not in shown


def test_should_read_the_hotels_own_site_and_osm_tags_as_sources():
    engine, maker = maker_for("wishes")
    site = "https://hotel.example/ru"
    reader = FakeReader(
        "Номера и цены.\nРазмещение с животными весом до 5 кг возможно за доплату 1000 ₽ в сутки."
    )
    client = FakeClient(
        [
            {
                "wish": DOG,
                "verdict": "yes",
                "quote": "Размещение с животными весом до 5 кг возможно за доплату 1000 ₽ в сутки",
                "source": 1,
                "note": "до 5 кг, 1000 ₽ в сутки",
            }
        ]
    )
    with_site = hotel(2, "Ривьера", website=site, tags={"dog": "yes"})
    try:
        found = asyncio.run(finder(maker, client, FakeSearch(), reader).check(SOCHI, [with_site], [DOG]))
    finally:
        asyncio.run(engine.dispose())

    assert found[with_site.id] == (
        Evidence(
            DOG,
            "yes",
            "Размещение с животными весом до 5 кг возможно за доплату 1000 ₽ в сутки",
            "до 5 кг, 1000 ₽ в сутки",
            "сайт отеля",
            site,
        ),
    )
    assert reader.urls == [site] and "dog=yes" in client.prompts[0]


def test_should_remember_answers_so_the_next_search_asks_nobody():
    engine, maker = maker_for("wishes")
    search = FakeSearch(
        [WebResult("https://otzovik.com/r", "Отзыв", "С собакой не пустили, животные запрещены.")]
    )
    client = FakeClient(
        [
            {
                "wish": DOG,
                "verdict": "no",
                "quote": "С собакой не пустили, животные запрещены",
                "source": 1,
                "note": None,
            }
        ]
    )
    strict = hotel(3, "Строгий")

    async def scenario():
        first = await finder(maker, client, search).check(SOCHI, [strict], [DOG])
        again = await finder(maker, client, search).check(SOCHI, [strict], [DOG])
        return first, again

    try:
        first, again = asyncio.run(scenario())
    finally:
        asyncio.run(engine.dispose())

    assert first == again and first[strict.id][0].verdict == "no"
    assert len(search.queries) == 1 and len(client.prompts) == 1


def test_should_answer_within_the_budget_and_finish_slow_checks_in_the_background():
    engine, maker = maker_for("wishes")
    search = FakeSearch(
        [WebResult("https://otzovik.com/r", "Отзыв", "Окна выходят на море, вид на море чудесный.")],
        delay=0.3,
    )
    client = FakeClient(
        [{"wish": SEA, "verdict": "yes", "quote": "вид на море чудесный", "source": 1, "note": None}]
    )
    slow = hotel(4, "Медленный")

    async def scenario():
        hurried = finder(maker, client, search, budget_s=0.05)
        now = await hurried.check(SOCHI, [slow], [SEA])
        await hurried.settle()
        later = await finder(maker, client, search).check(SOCHI, [slow], [SEA])
        return now, later

    try:
        now, later = asyncio.run(scenario())
    finally:
        asyncio.run(engine.dispose())

    assert now == {}  # not checked yet: the plan is not held up
    assert later[slow.id][0].verdict == "yes" and len(search.queries) == 1


def test_should_say_unknown_without_asking_the_model_when_nothing_was_found():
    engine, maker = maker_for("wishes")
    client = FakeClient([])
    quiet = hotel(5, "Тихий")
    try:
        found = asyncio.run(finder(maker, client, FakeSearch()).check(SOCHI, [quiet], [SEA, DOG]))
    finally:
        asyncio.run(engine.dispose())

    assert found[quiet.id] == (Evidence(SEA, "unknown"), Evidence(DOG, "unknown"))
    assert client.prompts == []


def test_should_check_only_the_best_candidates_and_the_hotel_the_user_named():
    engine, maker = maker_for("wishes")
    search = FakeSearch()
    many = [hotel(i, f"Отель {i}", stars=3 + i % 3) for i in range(10, 22)]
    source = HotelSource(evidence=finder(maker, FakeClient([]), search))
    try:
        checked = asyncio.run(source.checked(SOCHI, many, [SEA], Party(2), level=2, prefer=many[-1].id))
    finally:
        asyncio.run(engine.dispose())

    asked = [q.split(" Сочи")[0] for q in search.queries]
    assert many[-1].name in asked and len(asked) == 5
    assert [h.id for h in checked] == [h.id for h in many]  # the same hotels, in the same order
    assert sum(1 for h in checked if h.evidence) == 5


def test_should_rule_out_a_hotel_whose_source_says_no_and_prefer_confirmed_wishes():
    no = hotel(
        1,
        "Пять звёзд",
        stars=5,
        evidence=(
            Evidence(
                DOG, "no", "Размещение с животными не допускается", None, "сайт отеля", "https://a.example"
            ),
        ),
    )
    yes = hotel(
        2,
        "Для собак",
        stars=3,
        evidence=(
            Evidence(DOG, "yes", "Можно с собаками", "до 5 кг", "otzovik.com", "https://otzovik.com/r"),
        ),
    )
    unknown = hotel(3, "Неизвестно", stars=4, evidence=(Evidence(DOG, "unknown"),))

    pick = choose_hotel([no, yes, unknown], Party(2), Wishes(pets=True), 2, 3)

    assert pick.best.hotel.name == "Для собак"
    assert [(h.name, why) for h, why in pick.excluded] == [
        ("Пять звёзд", "«можно с собакой»: «Размещение с животными не допускается» (сайт отеля)")
    ]
    assert pick.unmet == [] and pick.best.misses == []
    assert [a.hotel.name for a in pick.alternatives] == ["Неизвестно"]  # its proof travels with it, unknown


def test_should_say_when_no_hotel_confirms_a_wish():
    hotels = [hotel(i, evidence=(Evidence(SEA, "unknown"),)) for i in range(1, 5)]

    pick = choose_hotel(hotels, Party(2), Wishes(), 2, 3)

    assert pick.unmet == [
        "Отеля, где подтверждено «с видом на море», не нашёл: беру лучший по остальному, уточним при бронировании"
    ]
    assert not any("животными" in u for u in pick.unmet)


def test_should_list_osm_hotels_with_the_seed_in_the_source():
    class Live:
        async def around(self, place):
            return osm_listed(NOMINATIM, place)

    source = HotelSource(listing=lambda pid: (), live=Live())

    names = [h.name for h in asyncio.run(source.listing(SOCHI))]

    assert names == ["Hyatt Regency Sochi", "City Park Hotel"]
    few = asyncio.run(source.hotels(SOCHI, date(2026, 11, 6), 3, Party(2)))
    assert not any(h.real for h in few)  # two real hotels are too few: the labelled demo set stands in


class Checker:
    """Says no for the first candidate and yes for the second: whatever the order, the plan must follow it."""

    def __init__(self):
        self.named: dict[str, str] = {}

    async def check(self, place, hotels, wishes):
        no, yes = hotels[0], hotels[1]
        self.named = {"no": no.name, "yes": yes.name}
        return {
            no.id: (
                Evidence(
                    wishes[0],
                    "no",
                    "Размещение с животными запрещено",
                    None,
                    "сайт отеля",
                    "https://a.example",
                ),
            ),
            yes.id: (
                Evidence(
                    wishes[0],
                    "yes",
                    "Можно с собакой до 5 кг",
                    "до 5 кг",
                    "otzovik.com",
                    "https://otzovik.com/r",
                ),
            ),
        }


def test_should_build_the_plan_and_more_hotels_with_the_checked_wishes(sessionmaker):  # noqa: F811
    checker = Checker()
    state = TripState(COUPLE.model_copy(update={"wishes": ["можно с собакой", "без пересадок"]}))
    registry = ToolRegistry(
        plan_tools(state, sessionmaker, flights=TICKETS, hotels=HotelSource(evidence=checker))
    )

    built = json.loads(call(registry, "build_trip", {"id": "kazan"}).content)
    stop = built["stops"][0]

    assert stop["hotel"]["name"] == checker.named["yes"]
    assert stop["hotel"]["wishes"] == ["можно с собакой: подтверждено (до 5 кг), otzovik.com"]
    assert any(checker.named["no"] in r and "запрещено" in r for r in stop["ruled_out"])
    shown = call(registry, "search_hotels", {"place": "kazan", "limit": 4})
    cards = shown.event["hotels"]
    assert cards[0]["name"] == checker.named["yes"] and cards[0]["evidence"][0]["verdict"] == "yes"
    assert checker.named["no"] not in [c["name"] for c in cards]
    assert json.loads(shown.content)["ruled_out"] == [
        f"{checker.named['no']}: можно с собакой: нет, сайт отеля"
    ]


def test_should_price_hotels_that_joined_the_list_after_the_stay_was_cached():
    from app.hotels.cache import CachedOffers
    from app.hotels.offers import EstimatedOffers, StayQuery

    class Counting(EstimatedOffers):
        calls = 0

        async def offers(self, place, hotels, stay):
            Counting.calls += 1
            return await super().offers(place, hotels, stay)

    cache = CachedOffers(Counting())
    stay = StayQuery("sochi", date(2026, 11, 6), 3)
    seed = [listed(1, "Старый")]
    grown = [*seed, listed(2, "Новый из OSM")]

    async def scenario():
        await cache.offers(SOCHI, seed, stay)
        return await cache.offers(SOCHI, grown, stay)

    found = asyncio.run(scenario())

    assert set(found) == {"sochi-hq1", "sochi-hq2"} and Counting.calls == 2


class FailingSearch:
    def __init__(self):
        self.queries: list[str] = []

    async def search(self, query: str):
        self.queries.append(query)
        raise httpx.HTTPStatusError(
            "429", request=httpx.Request("POST", "https://x"), response=httpx.Response(429)
        )


def test_should_check_a_hotel_once_while_two_searches_wait_for_it():
    engine, maker = maker_for("wishes")
    search = FakeSearch(
        [WebResult("https://otzovik.com/r", "Отзыв", "Вид на море из каждого номера.")], delay=0.1
    )
    client = FakeClient(
        [{"wish": SEA, "verdict": "yes", "quote": "Вид на море из каждого номера", "source": 1, "note": None}]
    )
    busy = hotel(6, "Популярный")
    checker = finder(maker, client, search)

    async def scenario():
        return await asyncio.gather(checker.check(SOCHI, [busy], [SEA]), checker.check(SOCHI, [busy], [SEA]))

    try:
        first, second = asyncio.run(scenario())
    finally:
        asyncio.run(engine.dispose())

    assert first == second and first[busy.id][0].verdict == "yes"
    assert len(search.queries) == 1 and len(client.prompts) == 1


def test_should_keep_what_the_site_says_when_the_review_search_fails_and_ask_again_later():
    engine, maker = maker_for("wishes")
    site = "https://hotel.example"
    reader = FakeReader("Во всех номерах есть ванна и душ.")
    client = FakeClient(
        [
            {
                "wish": BATH,
                "verdict": "yes",
                "quote": "Во всех номерах есть ванна и душ",
                "source": 1,
                "note": None,
            },
            {"wish": SEA, "verdict": "unknown", "quote": None, "source": None, "note": None},
        ]
    )
    failing = FailingSearch()
    with_site = hotel(7, "С сайтом", website=site)

    async def scenario():
        now = await finder(maker, client, failing, reader).check(SOCHI, [with_site], [BATH, SEA])
        again = await finder(maker, client, failing, reader).check(SOCHI, [with_site], [BATH, SEA])
        return now, again

    try:
        now, again = asyncio.run(scenario())
    finally:
        asyncio.run(engine.dispose())

    assert [e.verdict for e in now[with_site.id]] == ["yes", "unknown"]
    assert (
        len(failing.queries) == 2
    )  # «unknown» after a failed search is not kept: the reviews are asked again
    assert again == now


def test_should_not_reuse_an_answer_from_a_site_that_is_excluded_now():
    engine, maker = maker_for("wishes")
    search = FakeSearch(
        [WebResult("https://www.zenhotels.com/hotel/x", "Zen", "Dogs up to 40 cm are allowed.")]
    )
    old = FakeClient(
        [{"wish": DOG, "verdict": "yes", "quote": "Dogs up to 40 cm are allowed", "source": 1, "note": None}]
    )
    zen = hotel(8, "Старый ответ")

    async def scenario():
        checker = finder(maker, old, search)
        await checker._save(
            zen.id,
            (
                Evidence(
                    DOG,
                    "yes",
                    "Dogs up to 40 cm are allowed",
                    None,
                    "zenhotels.com",
                    "https://www.zenhotels.com/hotel/x",
                ),
            ),
        )
        return await finder(maker, FakeClient([]), FakeSearch()).check(SOCHI, [zen], [DOG])

    try:
        found = asyncio.run(scenario())
    finally:
        asyncio.run(engine.dispose())

    assert found[zen.id] == (Evidence(DOG, "unknown"),)  # checked again, without the excluded site


def test_should_not_ask_nominatim_again_right_after_it_failed():
    engine, maker = maker_for("osm")
    requests: list[httpx.Request] = []

    def hanging(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        raise httpx.ConnectTimeout("no answer", request=request)

    osm = OsmHotels(maker, transport=httpx.MockTransport(hanging))

    async def scenario():
        return await osm.around(SOCHI), await osm.around(SOCHI)

    try:
        first, second = asyncio.run(scenario())
    finally:
        asyncio.run(engine.dispose())

    assert first == second == [] and len(requests) == 1  # an outage costs one wait, not one per search


def test_should_not_list_the_chosen_hotel_as_ruled_out_when_every_hotel_says_no():
    no = Evidence(DOG, "no", "Животные запрещены", None, "сайт отеля", "https://a.example")
    hotels = [hotel(i, evidence=(no,)) for i in range(1, 5)]

    pick = choose_hotel(hotels, Party(2), Wishes(pets=True), 2, 3)

    assert pick.excluded == []
    assert pick.unmet == [
        "Отеля, где подтверждено «можно с собакой», не нашёл: беру лучший по остальному, уточним при бронировании"
    ]


def test_should_check_at_most_five_wishes_and_each_once():
    wishes = ["с видом на море", "с ванной", "балкон", "бассейн", "кухня", "парковка", "спа", "фитнес"]

    assert hotel_wishes(wishes) == wishes[:5]
    assert hotel_wishes(["с ванной", "отель с видом на море", "отель с ванной"]) == [
        "с ванной",
        "отель с видом на море",
    ]


def test_should_rule_out_a_hotel_only_on_its_own_word_and_rank_a_bad_review_lower():
    review_no = Evidence(DOG, "no", "С собакой не пустили", None, "otzovik.com", "https://otzovik.com/r")
    site_no = Evidence(DOG, "no", "Размещение с животными запрещено", None, "сайт отеля", "https://a.example")
    reviewed = hotel(1, "Плохой отзыв", stars=5, evidence=(review_no,))
    strict = hotel(2, "Запрещено на сайте", stars=5, evidence=(site_no,))
    unknown = hotel(3, "Неизвестно", stars=3, evidence=(Evidence(DOG, "unknown"),))

    pick = choose_hotel([reviewed, strict, unknown], Party(2), Wishes(pets=True), 2, 3)

    assert [h.name for h, _ in pick.excluded] == ["Запрещено на сайте"]
    assert pick.best.hotel.name == "Неизвестно"  # one guest's story is not the hotel's rule, but it counts


def test_should_not_take_an_answer_meant_for_another_wish():
    engine, maker = maker_for("wishes")
    search = FakeSearch([WebResult("https://otzovik.com/r", "Отзыв", "В номере большая ванна с джакузи.")])
    client = FakeClient(
        [
            {
                "wish": "что-то другое",
                "verdict": "yes",
                "quote": "В номере большая ванна с джакузи",
                "source": 1,
                "note": None,
            }
        ]
    )
    other = hotel(9, "Перепутанный")
    try:
        found = asyncio.run(finder(maker, client, search).check(SOCHI, [other], [SEA]))
    finally:
        asyncio.run(engine.dispose())

    assert found[other.id] == (Evidence(SEA, "unknown"),)


def test_should_merge_only_the_same_hotel_and_the_nearest_one():
    far = {
        **NOMINATIM[0],
        "osm_id": 66,
        "lat": "43.62",
    }  # the same name 5 km away: another hotel of the chain
    seed = (listed(1, "Hyatt Regency Sochi", stars=None),)

    merged = merge_listings(seed, osm_listed([far, NOMINATIM[0]], SOCHI))

    assert [h.id for h in merged] == ["sochi-hq1", "sochi-hon66"]
    assert merged[0].website == "https://hyatt.com/sochi"


def test_should_still_say_what_nobody_checked_when_another_wish_was_checked():
    from app.plan.hotels import WISH_WORDS

    hotels = [
        hotel(i, evidence=(Evidence(DOG, "yes", "Можно с собакой", None, "otzovik.com", "https://o.ru"),))
        for i in range(1, 5)
    ]

    pick = choose_hotel(hotels, Party(2), Wishes(pets=True, beach=True), 2, 3)

    assert "first line" in WISH_WORDS["beach"]
    assert any("пляжа" in u for u in pick.unmet)  # the beach wish was never checked, so it is still said
    assert not any("животными" in u for u in pick.unmet)  # the dog wish was


def test_should_pass_only_a_short_quote_when_a_hotel_is_ruled_out():
    long_quote = "Размещение с животными запрещено. " * 10
    site_no = Evidence(DOG, "no", long_quote, None, "сайт отеля", "https://a.example")
    hotels = [hotel(1, "Строгий", evidence=(site_no,)), hotel(2, "Другой")]

    pick = choose_hotel(hotels, Party(2), Wishes(pets=True), 2, 3)

    ((_, why),) = pick.excluded
    assert why.startswith(f"«{DOG}»: «Размещение с животными запрещено.") and len(why) < 200


def test_should_ask_the_model_why_before_its_verdict():
    client = FakeClient(
        [
            {
                "wish": SEA,
                "why": "сказано про вид на море из номеров",
                "verdict": "yes",
                "quote": "Номера с видом на море",
                "source": 1,
                "note": None,
            }
        ]
    )

    found = asyncio.run(
        WishJudge(client, "test-model").judge(
            "Отель",
            "Сочи",
            [SEA],
            [Source("сайт отеля", "https://a.example", "Номера с видом на море и балконом.")],
        )
    )

    fields = list(client.schema["properties"]["wishes"]["items"]["properties"])
    assert fields.index("why") < fields.index("verdict")
    assert found[0].verdict == "yes"


def test_should_check_again_once_the_judge_has_changed(monkeypatch):
    engine, maker = maker_for("wishes")
    met = hotel(9, "Проверен старым судьёй")
    said = Evidence(
        DOG, "yes", "Нас встретила дружелюбная собака", None, "irecommend.ru", "https://irecommend.ru/x"
    )

    async def scenario():
        await finder(maker, FakeClient([]))._save(met.id, (said,))
        monkeypatch.setattr(evidence, "JUDGE_VERSION", evidence.JUDGE_VERSION + 1)
        return await finder(maker, FakeClient([]), FakeSearch()).check(SOCHI, [met], [DOG])

    try:
        found = asyncio.run(scenario())
    finally:
        asyncio.run(engine.dispose())

    assert found[met.id] == (Evidence(DOG, "unknown"),)
