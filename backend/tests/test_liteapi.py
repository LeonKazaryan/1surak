"""Live hotels from LiteAPI: the real price of the stay, the room it sells with its photos, and the guest's wishes
answered on that very room, strictly: a room that says no rules the hotel out, a silence is never a yes."""

import asyncio
import json
from datetime import date

import httpx

from app.catalog.catalog import load_catalog
from app.hotels import HotelSource
from app.hotels.amenities import judge, need_of
from app.hotels.cache import CachedOffers
from app.hotels.card import beds_text, live_card
from app.hotels.evidence import hotel_wishes, web_wishes
from app.hotels.liteapi import BASE_URL, LiteApi, LiteOffers, details_from, occupancies, offers_from, to_price
from app.hotels.live import LiveStays
from app.hotels.offers import StayQuery
from app.plan.hotels import Party, Wishes, choose_hotel
from app.plan.trip import choice_view

NHA_TRANG = load_catalog().find("nha_trang")
CHECK_IN = date(2026, 12, 10)
STAY = StayQuery("nha_trang", CHECK_IN, 7, 2, (5,), "KZ")
TODAY = date(2026, 10, 28)
PHOTO = "https://static.cupid.travel/rooms-large-pictures/{}.jpg"
FAILOVER = "https://q-xx.bstatic.com/xdata/images/hotel/max1200/{}.jpg"


def listed(i: int, stars: int, reviews: int) -> dict:
    return {
        "id": f"lp{i}",
        "name": f"Hotel {i}",
        "stars": stars,
        "rating": 8.8,
        "reviewCount": reviews,
        "latitude": 12.24,
        "longitude": 109.19,
        "main_photo": f"https://static.cupid.travel/hotels/{i}.jpg",
    }


def rate(name: str, room_id: int, total: float, board: str = "BI", refundable: bool = True) -> dict:
    infos = [{"cancelTime": "2026-12-06 10:00:00", "amount": total, "currency": "RUB"}] if refundable else []
    return {
        "name": name,
        "mappedRoomId": room_id,
        "boardType": board,
        "boardName": "",
        "retailRate": {"total": [{"amount": total, "currency": "RUB"}]},
        "cancellationPolicies": {
            "refundableTag": "RFN" if refundable else "NRFN",
            "cancelPolicyInfos": infos,
        },
        "paymentTypes": ["NUITEE_PAY"],
    }


def room_type(*rates: dict) -> dict:
    return {
        "offerRetailRate": {"amount": sum(r["retailRate"]["total"][0]["amount"] for r in rates)},
        "rates": list(rates),
    }


def room(room_id: int, name: str, views: list[str], amenities: list[str]) -> dict:
    return {
        "id": room_id,
        "roomName": name,
        "roomSizeSquare": 28,
        "roomSizeUnit": "sqm",
        "bedTypes": [{"quantity": 1, "bedType": "Queen bed"}],
        "views": [{"view": v} for v in views],
        "roomAmenities": [{"name": a} for a in amenities],
        "photos": [
            {
                "url": PHOTO.format(room_id),
                "hd_url": PHOTO.format(room_id),
                "failoverPhoto": FAILOVER.format(room_id),
                "mainPhoto": True,
            }
        ],
    }


LISTED = [listed(1, 4, 900), listed(2, 5, 1200), listed(3, 3, 300), listed(4, 4, 50)]
SHOWER = ["Shower", "Air conditioning", "Minibar", "Free WiFi", "Hair dryer", "Private bathroom"]
BATH = [*SHOWER, "Bathtub", "Balcony"]
RATES = [
    {
        "hotelId": "lp1",
        "roomTypes": [
            room_type(rate("Deluxe City View", 11, 30000)),
            room_type(rate("Superior Sea View", 12, 42000)),
        ],
    },
    {"hotelId": "lp2", "roomTypes": [room_type(rate("Ocean View King", 21, 90000, "RO", refundable=False))]},
    {"hotelId": "lp3", "roomTypes": [room_type(rate("Standard No Window", 31, 14000))]},
    {"hotelId": "lp4", "roomTypes": [room_type(rate("Studio", 41, 20000))]},
]
DETAILS = {
    "lp1": {
        "id": "lp1",
        "main_photo": "https://static.cupid.travel/hotels/1.jpg",
        "hotelImages": [{"url": "https://static.cupid.travel/hotels/1b.jpg", "defaultImage": False}],
        "hotelFacilities": ["Outdoor pool", "Free WiFi", "Kids' club", "Beachfront"],
        "rooms": [
            room(11, "Deluxe City View", ["City View"], SHOWER),
            room(12, "Superior Sea View", ["Sea View"], BATH),
        ],
        "petsAllowed": False,
        "policyAttributes": {
            "pets": {"allowed": None},
            "checkIn": {"from": "15:00"},
            "checkOut": {"until": "11:00"},
        },
        "sentiment_analysis": {
            "categories": [{"name": "Location", "rating": 9.07}, {"name": "Overall Experience", "rating": 9}]
        },
    },
    "lp2": {
        "id": "lp2",
        "hotelFacilities": ["Pets allowed", "Spa/wellness center"],
        "rooms": [room(21, "Ocean View King", ["Ocean View"], SHOWER)],
        "petsAllowed": True,
    },
    "lp3": {"id": "lp3", "hotelFacilities": [], "rooms": [room(31, "Standard No Window", [], SHOWER)]},
    "lp4": {
        "id": "lp4",
        "hotelFacilities": ["Adult only"],
        "rooms": [],
        "policyAttributes": {"pets": {"allowed": False}},
    },
}


def lite_api(calls: list[str] | None = None, fail: bool = False, asked: list | None = None) -> LiteApi:
    def answer(request: httpx.Request) -> httpx.Response:
        (calls if calls is not None else []).append(request.url.path)
        if fail:
            return httpx.Response(500, json={"error": {"code": 500, "message": "down"}})
        if request.url.path.endswith("/data/hotels"):  # around the point asked
            at = {
                "latitude": float(request.url.params["latitude"]),
                "longitude": float(request.url.params["longitude"]),
            }
            return httpx.Response(200, json={"data": [h | at for h in LISTED]})
        if request.url.path.endswith("/data/hotel"):
            return httpx.Response(200, json={"data": DETAILS[request.url.params["hotelId"]]})
        body = json.loads(request.content)
        (asked if asked is not None else []).append((body["checkin"], body["checkout"]))
        found = [r for r in RATES if r["hotelId"] in body["hotelIds"]]
        return httpx.Response(200, json={"data": found, "sandbox": True})

    client = httpx.AsyncClient(base_url=BASE_URL, transport=httpx.MockTransport(answer))
    return LiteApi("sand_test", client=client)


def source(api: LiteApi) -> HotelSource:
    stays = LiveStays(api, CachedOffers(LiteOffers(api, today=lambda: TODAY)), lambda: "KZ")
    return HotelSource(listing=lambda _: (), stays=stays)


FAMILY = Party(2, (5,))


def live(wishes: list[str], party: Party = FAMILY, api: LiteApi | None = None):
    async def run():
        hotels = source(api or lite_api())
        found = await hotels.hotels(NHA_TRANG, CHECK_IN, 7, party)
        return await hotels.checked(NHA_TRANG, found, wishes, party, 2)

    return asyncio.run(run())


def test_should_price_the_whole_stay_for_the_whole_party_with_its_room_and_refund():
    offers = offers_from(RATES, STAY, TODAY)

    city, sea = offers["lp1"]
    assert (city.room, city.room_id, city.stay_rub, city.night_rub) == ("Deluxe City View", "11", 30000, 4286)
    assert city.meal == "breakfast" and city.cancel_until == "2026-12-06" and city.free_cancel_days == 4
    ocean = offers["lp2"][0]
    assert ocean.meal == "room_only" and ocean.free_cancel_days is None and ocean.cancel_until is None
    assert all(o.kind == "real" and o.terms_known and o.source == "LiteAPI" for o in (city, sea, ocean))
    # two rooms: the offer's own total, not one room's price
    two = room_type(rate("Family", 5, 20000), rate("Family", 5, 20000))
    assert offers_from([{"hotelId": "x", "roomTypes": [two]}], STAY, TODAY)["x"][0].stay_rub == 40000


def test_should_put_the_party_in_rooms_with_an_adult_in_each():
    assert occupancies(2, (5,)) == [{"adults": 2, "children": [5]}]
    assert occupancies(4, ()) == [{"adults": 2, "children": []}, {"adults": 2, "children": []}]
    assert occupancies(2, (3, 8)) == [{"adults": 1, "children": [3]}, {"adults": 1, "children": [8]}]


def test_should_price_hotels_of_every_class_not_only_the_famous_ones():
    from app.hotels.liteapi import around_from

    picked = to_price(around_from(LISTED), 3)

    assert {a.stars for a in picked} == {3, 4, 5}


def test_should_keep_only_the_providers_own_photos_and_only_a_stated_pets_rule():
    lp1, lp2, lp4 = details_from(DETAILS["lp1"]), details_from(DETAILS["lp2"]), details_from(DETAILS["lp4"])

    assert lp1.photos == (
        "https://static.cupid.travel/hotels/1.jpg",
        "https://static.cupid.travel/hotels/1b.jpg",
    )
    assert all("bstatic" not in p for r in lp1.rooms for p in r.photos) and lp1.rooms[1].photos == (
        PHOTO.format(12),
    )
    # petsAllowed false is LiteAPI's default, not the hotel's word
    assert (lp1.pets, lp2.pets, lp4.pets) == (None, True, False)
    assert (lp1.check_in, lp1.check_out, lp1.scores) == ("15:00", "11:00", (("Location", 9.07),))


def test_should_know_which_wishes_it_can_answer_on_the_rooms():
    assert [
        need_of(w).key for w in ("с видом на море", "хочу с ванной", "можно с собакой", "всё включено")
    ] == [
        "sea_view",
        "bath",
        "pets",
        "all_inclusive",
    ]
    assert need_of("ванная комната") is None and need_of("спать до обеда") is None
    assert need_of("хороший интернет") is None  # its speed is in the reviews, not in a facility list
    wishes = hotel_wishes(["с видом на море", "всё включено", "с завтраком", "недорого"])
    assert wishes == ["с видом на море", "всё включено", "с завтраком"]
    assert web_wishes(wishes) == ["с видом на море"]  # only a rate knows the meal plan


def test_should_sell_the_room_that_has_the_wish_and_prove_it_with_the_data():
    best = choose_hotel(live(["с видом на море", "с ванной"]), Party(2, (5,)), Wishes(), 2, 7).best

    assert best.hotel.name == "Hotel 1"
    assert (
        best.rate.room == "Superior Sea View" and best.total_rub == 42000
    )  # the provider's total, to the rouble
    said = {e.wish: (e.verdict, e.quote) for e in best.hotel.evidence}
    assert said == {"с видом на море": ("yes", "Superior Sea View"), "с ванной": ("yes", "Bathtub")}


def test_should_rule_out_a_hotel_whose_rooms_say_no_and_never_take_silence_for_yes():
    hotels = {h.name: h for h in live(["с видом на море", "с ванной", "можно с собакой"])}

    def said(name: str) -> dict:
        return {e.wish: e.verdict for e in hotels[name].evidence}

    assert said("Hotel 1") == {"с видом на море": "yes", "с ванной": "yes", "можно с собакой": "unknown"}
    assert said("Hotel 2") == {"с видом на море": "yes", "с ванной": "no", "можно с собакой": "yes"}
    assert said("Hotel 3")["с видом на море"] == "no"  # «No Window»
    pick = choose_hotel(list(hotels.values()), Party(2, (5,)), Wishes(), 2, 7)
    out = {h.name: why for h, why in pick.excluded}
    assert out["Hotel 2"] == "«с ванной»: на ваши даты таких номеров нет"
    assert "No Window" in out["Hotel 3"]
    assert out["Hotel 4"] == "«можно с собакой»: «Pets not allowed» (LiteAPI)"
    # adults only, and a child comes: out whatever the wishes
    family = choose_hotel(live([]), FAMILY, Wishes(), 2, 7)
    assert [(h.name, why) for h, why in family.excluded] == [
        ("Hotel 4", "только для взрослых, а с вами ребёнок")
    ]


def test_should_not_take_a_bath_or_shower_for_a_bath():
    rates = next(h for h in live([]) if h.name == "Hotel 1").rates
    details = details_from(
        {
            "id": "x",
            "rooms": [room(11, "Deluxe City View", [], [*SHOWER, "Bathtub or shower"])],
            "hotelFacilities": [],
        }
    )

    evidence, _ = judge(["с ванной"], rates[:1], details)

    assert evidence[0].verdict == "no"


def test_should_answer_meal_and_refund_wishes_on_the_rate():
    hotels = {h.name: h for h in live(["всё включено", "бесплатная отмена"])}

    lp1 = {e.wish: e for e in hotels["Hotel 1"].evidence}
    assert lp1["всё включено"].verdict == "no" and lp1["всё включено"].note == "на ваши даты только: завтраки"
    assert lp1["бесплатная отмена"].verdict == "yes"
    assert {e.wish: e.verdict for e in hotels["Hotel 2"].evidence}["бесплатная отмена"] == "no"


def test_should_show_the_booked_rooms_photos_first_and_say_the_room_in_russian():
    best = choose_hotel(live(["с видом на море"]), Party(2, (5,)), Wishes(), 2, 7).best

    view = choice_view(best)

    assert (
        view["photos"][0] == PHOTO.format(12) and "https://static.cupid.travel/hotels/1.jpg" in view["photos"]
    )
    assert view["room"] == {
        "name": "Superior Sea View",
        "size_m2": 28,
        "beds": "1 двуспальная кровать",
        "view": "вид на море",
        "amenities": ["кондиционер", "мини-бар", "Wi-Fi", "ванна", "балкон"],
        "photos": 1,
    }
    assert view["cancel_until"] == "2026-12-06" and view["price_source"] == "LiteAPI" and view["sandbox"]
    assert view["price_estimate"] is False and view["check_in"] == "15:00"
    assert view["scores"] == [{"label": "Расположение", "score": 9.1}]
    assert beds_text(((2, "Twin bed"), (1, "Sofa bed"))) == "2 односпальные кровати + 1 диван-кровать"
    assert live_card(best.hotel.__class__(**{**best.hotel.__dict__, "provider": None}), best.rate) == {}


def test_should_read_each_list_and_hotel_once_and_fall_back_when_the_provider_is_down():
    calls: list[str] = []
    api = lite_api(calls)
    live(["с видом на море"], api=api)
    live(["с видом на море"], api=api)

    assert calls.count("/v3.0/data/hotels") == 1 and calls.count("/v3.0/data/hotel") == 4
    assert calls.count("/v3.0/hotels/rates") == 2  # a new CachedOffers each run; one shared in the app

    down = asyncio.run(source(lite_api(fail=True)).hotels(NHA_TRANG, CHECK_IN, 7, Party()))
    assert down and not any(h.provider for h in down)  # the demo hotels still make a plan


def test_should_price_the_hotel_for_the_nights_really_spent_there():
    from tests.conftest import FakeFlights
    from tests.test_plan_assemble import build, flights, snap

    tickets = FakeFlights(
        {
            "AYT": flights(("2026-11-05T20:00:00+03:00", "AYT", 18_000, 600)),  # lands at 06:00 the next day
            "MOW": flights(("2026-11-12T15:00:00+03:00", "MOW", 17_000, 240)),
        }
    )
    asked: list = []

    plan = build([snap("antalya")], tickets=tickets, hotels=source(lite_api(asked=asked)))

    stop = plan.stops[0]
    assert plan.dates_fixed and (stop.check_in, stop.check_out) == (date(2026, 11, 6), date(2026, 11, 12))
    assert asked == [("2026-11-05", "2026-11-12"), ("2026-11-06", "2026-11-12")]
    assert (
        stop.pick.best.total_rub == stop.pick.best.rate.stay_rub
    )  # the provider's own price for those nights
