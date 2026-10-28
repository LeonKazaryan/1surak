"""Visas for the traveller's own passport: the Passport Index rule, the fee found on the web, and the cache."""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.flights import current_origin
from app.kb.web import WebResult
from app.visas import NoFees, VisaFees, area_of, configure, label, passport_of, rule_for, sentence, shared
from app.visas.fees import checked_fee
from app.visas.router import router

NOW = datetime(2026, 10, 26, 12, tzinfo=UTC)
STATE_DEPT = WebResult(
    url="https://travel.state.gov/content/travel/en/us-visas/visa-information-resources/fees.html",
    title="Fees for Visa Services",
    content="Non-petition based nonimmigrant visa (except E): Business/Tourist (B1/B2) visa application fee "
    "is $185. The fee is paid before the interview.",
)
AGENCY = WebResult(
    url="https://visa-agency.example/usa", title="Виза в США", content="Оформим визу в США за 450 $."
)


def test_should_take_the_passport_of_the_departure_country():
    assert passport_of("NQZ") == "KZ" and passport_of("MOW") == "RU" and passport_of(None) == "RU"


def test_should_read_the_rule_for_each_passport():
    us, china, nepal = rule_for("US", "KZ"), rule_for("CN", "KZ"), rule_for("NP", "KZ")

    assert (us.code, china.code, china.days, nepal.code) == ("visa_required", "visa_free", 30, "on_arrival")
    assert rule_for("KZ", "KZ").code == "none" and rule_for("TH", "RU").code == "visa_free"
    assert label(china) == "без визы до 30 дней" and label(us) == "нужна виза"
    assert sentence(us) == (
        "Для граждан Казахстана нужна виза в США, её оформляют заранее в консульстве или визовом центре."
    )
    assert sentence(nepal).startswith("Для граждан Казахстана виза в Непал ставится по прилёте")


def test_should_take_the_rule_for_the_current_departure_city():
    token = current_origin.set("ALA")
    try:
        assert rule_for("US").passport == "KZ"
    finally:
        current_origin.reset(token)
    assert rule_for("US").passport == "RU"  # the default departure city is Moscow


def test_should_know_which_countries_one_schengen_visa_opens():
    assert area_of("NL")["name"] == "Шенген"  # a member stated as the Kingdom's constituent country
    assert area_of("ro")["name"] == "Шенген"  # joined in 2025
    assert area_of("GB") is None and area_of("CY") is None  # their own visas
    assert area_of("GL") is None  # Denmark is in, Greenland is not


def test_should_show_one_schengen_visa_for_a_route_through_several_members():
    stays = [
        (rule_for(c, "KZ"), n) for c, n in (("IT", 3), ("ES", 3), ("ES", 3), ("PT", 3), ("GB", 2), ("TR", 2))
    ]

    chips = shared(stays)

    names = [chip["name"] for _, chip in chips]
    assert names == ["Шенген", "Великобритания"]  # Turkey needs no visa from Kazakhstan, so no chip
    rule, schengen = chips[0]
    assert schengen["countries"] == ["Италия", "Испания", "Португалия"] and schengen["label"] == "нужна виза"
    # applied for where most nights are spent: Barcelona and Madrid make Spain, and its fee is the one looked up
    assert rule.destination == "ES" and "одна на Италию, Испанию и Португалию" in schengen["text"]
    assert "Испании: там больше всего ночей" in schengen["text"]


def test_should_apply_for_a_shared_visa_where_the_trip_enters_when_the_nights_are_even():
    [(rule, chip)] = shared([(rule_for("AT", "KZ"), 3), (rule_for("CZ", "KZ"), 3)])

    assert rule.destination == "AT" and "Австрии: туда первый въезд" in chip["text"]
    [(_, islands)] = shared([(rule_for("GR", "KZ"), 3), (rule_for("MT", "KZ"), 3)])
    assert "одна на Грецию и Мальту" in islands["text"]  # Malta is «на Мальту», not «в»
    [(_, alone)] = shared([(rule_for("FR", "KZ"), 5)])
    assert alone["name"] == "Франция" and "countries" not in alone  # one member alone is just that country


TAKES_SCHENGEN = {
    "schengen": {
        "ME": {"days": 30, "multiple_entry": False, "source": "gov.me", "url": "https://www.gov.me/visa"},
        "MK": {"days": 15, "multiple_entry": True, "source": "mfa.gov.mk", "url": "https://mfa.gov.mk/visa"},
    }
}


def test_should_fold_a_country_that_takes_a_schengen_visa_into_its_chip(monkeypatch):
    from app.visas import rules

    monkeypatch.setattr(rules, "_accepted", lambda: TAKES_SCHENGEN)
    stays = [(rule_for(c, "KZ"), 3) for c in ("GR", "MK", "ME", "IT")]

    [(rule, chip)] = shared(stays)  # one visa for the whole trip, not four

    assert chip["name"] == "Шенген" and chip["countries"] == ["Греция", "Италия"]
    assert [a["name"] for a in chip["also"]] == ["Северная Македония", "Черногория"]
    assert "По ней же пускают в Северную Македонию (до 15 дней) и в Черногорию (до 30 дней)" in chip["text"]
    # out of Schengen to the Balkans and back into Italy: a single-entry visa would end the trip at the border
    assert chip["label"] == "нужна многократная виза" and "многократная" in chip["text"]
    assert rule.destination == "GR"  # nights are even among the members: where the trip enters


def test_should_keep_a_countrys_own_visa_when_no_member_of_the_area_is_on_the_route(monkeypatch):
    from app.visas import rules

    monkeypatch.setattr(rules, "_accepted", lambda: TAKES_SCHENGEN)

    chips = shared([(rule_for("ME", "KZ"), 3), (rule_for("TR", "KZ"), 3)])

    assert [chip["name"] for _, chip in chips] == ["Черногория"]  # no Schengen visa to lean on
    [(_, one_entry)] = shared([(rule_for("IT", "KZ"), 3), (rule_for("ME", "KZ"), 3)])
    assert one_entry["label"] == "нужна виза"  # Montenegro last: the trip never comes back into Schengen
    [(_, strict)] = shared([(rule_for("IT", "KZ"), 3), (rule_for("MK", "KZ"), 3)])
    assert "Северная Македония пускает только по ней" in strict["text"]  # its own rule, not a way back


def test_should_take_a_country_as_letting_a_schengen_visa_in_only_for_everyone_and_with_no_other_permit():
    from scripts.build_visa_accepts_seed import NAMES, checked

    names = NAMES["schengen"][2]
    page = WebResult(
        url="https://www.gov.me/en/visas",
        title="Visa regime",
        content="Foreigners holding a valid Schengen visa may enter Montenegro without a visa for up to 30 days.",
    )
    quote = "holding a valid Schengen visa may enter Montenegro without a visa for up to 30 days"
    answer = {
        "accepts": True,
        "days": 30,
        "multiple_entry": False,
        "for_everyone": True,
        "still_needs": "none",
    }

    taken = checked({**answer, "source": 1, "quote": quote}, [page], names)

    assert taken["days"] == 30 and taken["source"] == "gov.me"
    for wrong in ({"still_needs": "eta"}, {"still_needs": "on_arrival"}, {"for_everyone": False}):
        assert checked({**answer, **wrong, "source": 1, "quote": quote}, [page], names) is None
    border = WebResult(
        url=page.url, title="", content="Holders of a used Schengen visa may obtain a visa on arrival."
    )
    on_arrival = {
        **answer,
        "source": 1,
        "quote": "Holders of a used Schengen visa may obtain a visa on arrival",
    }
    assert checked(on_arrival, [border], names) is None  # the model said «none», the quote says otherwise
    assert checked({**answer, "source": 1, "quote": "may enter for up to 30 days"}, [page], names) is None


def test_should_take_a_fee_only_when_its_quote_and_sum_are_on_the_page():
    good = {"found": True, "amount": 185, "currency": "usd", "covers": "консульский сбор B1/B2", "source": 1}
    results = [STATE_DEPT, AGENCY]
    quote = "Business/Tourist (B1/B2) visa application fee is $185"

    fee = checked_fee({**good, "quote": quote}, results, NOW.date())

    assert (fee.amount, fee.currency, fee.source) == (185, "USD", "travel.state.gov")
    assert checked_fee({**good, "quote": "the fee is $160"}, results, NOW.date()) is None  # not on the page
    assert (
        checked_fee({**good, "amount": 160, "quote": quote}, results, NOW.date()) is None
    )  # not in the quote
    assert checked_fee({**good, "source": 3, "quote": quote}, results, NOW.date()) is None
    assert checked_fee({**good, "found": False, "quote": quote}, results, NOW.date()) is None


class Search:
    def __init__(self, results):
        self.results, self.asked = results, []

    async def search(self, query):
        self.asked.append(query)
        await asyncio.sleep(0.01)
        return self.results


def model_answering(answer: dict):
    calls = []

    async def create(**kwargs):
        calls.append(kwargs)
        message = SimpleNamespace(content=json.dumps(answer))
        return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=None)

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    return client, calls


ANSWER = {
    "found": True,
    "amount": 185,
    "currency": "USD",
    "covers": "консульский сбор за туристическую визу B1/B2",
    "source": 1,
    "quote": "Business/Tourist (B1/B2) visa application fee is $185",
}


def test_should_look_a_fee_up_once_and_keep_it():
    search, (client, calls) = Search([STATE_DEPT]), model_answering(ANSWER)
    fees = VisaFees(None, [search], client, "m", now=lambda: NOW)
    rule = rule_for("US", "KZ")

    async def run():
        together = await asyncio.gather(*(fees.get(rule) for _ in range(3)))
        return together, await fees.get(rule)

    together, later = asyncio.run(run())

    assert all(f.amount == 185 for f in together) and later.source == "travel.state.gov"
    assert len(calls) == 1 and len(search.asked) == 1  # three cards and a hover: one search, one read
    assert "United States tourist visa fee for Kazakhstan citizens 2026" in search.asked[0]
    assert fees.known(rule).view()["rub"] == round(185 / 0.012416)


def test_should_remember_a_miss_for_a_while_and_then_look_again():
    clock = [NOW]
    search, (client, _) = Search([AGENCY]), model_answering({**ANSWER, "found": False})
    fees = VisaFees(None, [search], client, "m", now=lambda: clock[0])
    rule = rule_for("GB", "KZ")

    assert (
        asyncio.run(fees.get(rule)) is None and len(search.asked) == 2
    )  # English and Russian, read together
    assert asyncio.run(fees.get(rule)) is None and len(search.asked) == 2
    clock[0] = NOW + timedelta(days=3)
    asyncio.run(fees.get(rule))
    assert len(search.asked) == 4


def test_should_not_look_up_a_fee_where_no_visa_is_needed():
    search, (client, _) = Search([STATE_DEPT]), model_answering(ANSWER)
    fees = VisaFees(None, [search], client, "m", now=lambda: NOW)

    asyncio.run(fees.warm([rule_for("CN", "KZ"), rule_for("GE", "KZ")]))

    assert search.asked == []


def test_should_answer_the_chip_with_the_rule_and_the_fee():
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)
    client, _ = model_answering(ANSWER)
    configure(VisaFees(None, [Search([STATE_DEPT])], client, "m", now=lambda: NOW))
    try:
        answer = TestClient(app).get("/api/visa/kz-us").json()
    finally:
        configure(NoFees())

    assert answer["text"].startswith("Для граждан Казахстана нужна виза в США")
    assert (answer["fee"]["amount"], answer["fee"]["currency"], answer["pair"]) == (185, "USD", "KZ-US")
    assert TestClient(app).get("/api/visa/xx").status_code == 422


def test_should_take_a_free_visa_only_with_words_that_say_so():
    page = WebResult(
        url="https://www.kz.emb-japan.go.jp/visa.html",
        title="Visa",
        content="The visa fee for citizens of Kazakhstan is free of charge for short-term stay.",
    )
    free = {"found": True, "amount": 0, "currency": "JPY", "covers": "виза", "source": 1}

    fee = checked_fee({**free, "quote": "is free of charge for short-term stay"}, [page], NOW.date())

    assert fee.amount == 0 and fee.for_model().startswith("бесплатно")
    assert (
        checked_fee({**free, "quote": "The visa fee for citizens of Kazakhstan"}, [page], NOW.date()) is None
    )


class Limited:
    def __init__(self):
        self.asked = 0

    async def search(self, query):
        self.asked += 1
        raise RuntimeError("429 Too Many Requests")


def test_should_hand_over_to_the_next_search_when_one_is_rate_limited():
    limited, backup, (client, _) = Limited(), Search([STATE_DEPT]), model_answering(ANSWER)
    fees = VisaFees(None, [limited, backup], client, "m", now=lambda: NOW)

    fee = asyncio.run(fees.get(rule_for("US", "KZ")))

    assert fee.amount == 185 and limited.asked == 1 and len(backup.asked) == 1


def test_should_not_remember_a_miss_for_days_when_no_search_answered():
    client, _ = model_answering(ANSWER)
    fees = VisaFees(None, [Limited()], client, "m", now=lambda: NOW)

    assert asyncio.run(fees.get(rule_for("US", "KZ"))) is None
    assert fees.cache.ttl_of("KZ-US") == timedelta(minutes=10)  # tried again soon, not in two days
