"""Memory from the traveller's earlier trips in this browser: what it remembers, what it offers, what it leaves to
them. Nothing is stored apart from the chats: deleting a chat or hiding a fact forgets it."""

import asyncio
import json
from datetime import date

from app.chats import repository
from app.chats.service import _offer_nudge
from app.memory import ideas, nudge, party_text, remember
from app.money import CURRENCIES, current_currency
from app.tools import ToolRegistry
from app.trip import TripBrief, TripState, trip_tools

TODAY = date(2026, 10, 28)


def chat(chat_id: str, updated: str, title: str = "Поездка", **brief) -> dict:
    return {"id": chat_id, "title": title, "updated_at": f"{updated}T12:00:00+00:00", "brief": brief}


HURGHADA = chat(
    "c-hurghada",
    "2025-10-02",
    destination="Хургада",
    month=11,
    adults=2,
    children=1,
    children_ages=[5],
    kinds=["sea"],
    budget_level=3,
    visa_free_only=False,
    wishes=["с видом на море", "на рождество"],
    booked={
        "number": "1S-ABC234",
        "name": "Хургада",
        "span": "10–17 ноября",
        "from": "2025-11-10",
        "to": "2025-11-17",
    },
)
ROME = chat(
    "c-rome",
    "2026-10-20",
    destination="Рим",
    month=11,
    kinds=["sea", "city"],
    by_land=True,
    plan={"name": "Рим", "check_in": "2026-11-20", "check_out": "2026-11-27"},
)


def test_should_remember_who_travels_with_the_children_a_year_older():
    memory = remember([ROME, HURGHADA], TODAY)

    assert memory.party == {"adults": 2, "children": 1, "children_ages": [6]}  # five a year ago
    assert memory.fact("party").text == "двое взрослых + ребёнок 6 лет"
    assert memory.fact("party").source == "Хургада · ноябрь"


def test_should_keep_a_budget_only_while_it_is_recent():
    assert remember([HURGHADA], TODAY).budget is None  # a year old: asked again, not offered
    fresh = chat("c-1", "2026-09-01", budget_total=500_000, budget_currency="KZT")

    memory = remember([fresh], TODAY)

    assert memory.budget == {"budget_total": 500_000, "budget_currency": "KZT"}
    assert memory.fact("budget").text.startswith("до 500")


def test_should_take_only_wishes_about_the_hotel_and_tastes_from_a_few_trips():
    memory = remember([ROME, HURGHADA], TODAY)

    assert memory.wishes == ["с видом на море"]  # «на рождество» was about that trip, not the traveller
    assert memory.kinds == ["sea"]  # in both trips; the city only once
    assert memory.by_land and memory.fact("by_land").text == "поездом, а не самолётом"
    assert memory.fact("trip:c-hurghada").label == "Были"
    assert memory.fact("seen:c-rome").text == "Рим"  # a plan put together and left
    older = chat("c-old", "2026-10-10", shown=["antalya"])
    assert [f.key for f in remember([ROME, older], TODAY).facts if f.label == "Смотрели"] == ["seen:c-rome"]


def test_should_forget_a_hidden_fact_and_offer_nothing_from_it():
    memory = remember([ROME, HURGHADA], TODAY, forget={"party", "wish:с видом на море"})

    assert memory.party is None and memory.fact("party") is None
    assert memory.wishes == [] and memory.cards(["travelers"]) == {}


def test_should_offer_on_the_cards_only_what_they_ask():
    memory = remember([HURGHADA], TODAY)

    offered = memory.cards(["travelers", "visa"])

    assert set(offered) == {"travelers", "visa"}
    assert (
        offered["travelers"]["children_ages"] == [6] and offered["travelers"]["source"] == "Хургада · ноябрь"
    )
    assert offered["visa"]["visa_free_only"] is False


def test_should_offer_a_budget_in_the_currency_counted_now():
    memory = remember([chat("c-1", "2026-09-01", budget_total=500_000, budget_currency="KZT")], TODAY)
    token = current_currency.set(CURRENCIES["RUB"])
    try:
        offered = memory.cards(["budget"])["budget"]
    finally:
        current_currency.reset(token)

    assert offered["budget_currency"] == "RUB" and offered["budget_total"] % 1000 == 0


def test_should_word_the_party_as_people_say_it():
    assert party_text(1, [], 0) == "один" and party_text(2, [], 0) == "вдвоём"
    assert (
        party_text(2, [3, 8], 2) == "двое взрослых + дети 3 и 8 лет"
    )  # «вдвоём с детьми» could be one adult
    assert party_text(1, [6], 1, joiner=" и ") == "взрослый и ребёнок 6 лет"
    assert party_text(3, [], 1) == "3 взрослых + 1 ребёнок"


def test_should_suggest_once_what_was_wished_last_time_and_not_said_now():
    memory = remember([HURGHADA], TODAY)

    assert nudge(memory, TripBrief())["text"] == "Как в прошлый раз: с видом на море"
    assert nudge(memory, TripBrief(wishes=["С видом на море"])) is None  # said this time: nothing to suggest
    trip = TripState(TripBrief(), memory=memory)
    _offer_nudge(trip, [{"type": "destinations"}])
    first = trip.brief.nudge
    trip.brief = trip.brief.model_copy(update={"nudge": None})
    _offer_nudge(trip, [{"type": "trip_plan"}])
    assert first and trip.brief.nudge is None  # once in a trip


def test_should_open_the_start_screen_with_the_trip_coming_and_the_one_left():
    soon = chat(
        "c-soon",
        "2026-10-25",
        booked={
            "number": "1S-XYZ789",
            "name": "Анталья",
            "span": "9–16 ноября",
            "from": "2026-11-09",
            "to": "2026-11-16",
        },
    )

    found = ideas(remember([soon, ROME, HURGHADA], TODAY), TODAY)

    assert found[0] == {
        "label": "Анталья: через 12 дней",
        "query": "Что взять с собой и какая погода будет на мои даты?",
        "chat_id": "c-soon",
        "why": "бронь 1S-XYZ789",
    }
    assert found[1]["label"] == "Вернуться: Рим" and found[1]["chat_id"] == "c-rome"
    assert found[2]["label"] == "Море в ноябре с детьми"
    assert found[2]["query"] == "Хочу к тёплому морю в ноябре, двое взрослых и ребёнок 6 лет, поездом"
    assert found[2]["why"].startswith("помню: двое взрослых + ребёнок 6 лет")


def test_should_suggest_ideas_for_anyone_without_a_trip_and_never_twice():
    cold = ideas(remember([], TODAY), TODAY)
    assert [i["label"] for i in cold] == [
        "Тёплое море в ноябре",
        "Несколько стран за 10 дней",
        "Выходные недалеко",
    ]
    assert all(i["why"] is None for i in cold)

    warm = ideas(remember([HURGHADA], TODAY), TODAY)
    assert not any(i["label"].startswith("Тёплое море") for i in warm)  # the personal sea idea covers it


def test_should_offer_memory_on_the_cards_and_to_the_model_without_applying_it():
    state = TripState(TripBrief(), memory=remember([HURGHADA], TODAY))
    registry = ToolRegistry(trip_tools(state, None))  # neither tool reads the database

    found = asyncio.run(
        registry.execute("update_trip_brief", json.dumps({"destination": "Турция", "month": 12}))
    )
    asked = asyncio.run(registry.execute("ask_user", json.dumps({"intro": "Уточню"})))

    assert any("двое взрослых + ребёнок 6 лет" in line for line in json.loads(found.content)["remembered"])
    assert state.brief.adults is None  # remembered, not applied
    assert asked.event["remembered"]["travelers"]["text"] == "двое взрослых + ребёнок 6 лет"


def test_should_answer_the_start_screen_from_the_browsers_trips(client):
    chat_id = client.post("/api/chat/stream", json={"query": "Хургада"}).text
    chat_id = json.loads(chat_id.strip().splitlines()[-1])["chat_id"]
    client.portal.call(_save_brief, client.app.state.sessionmaker, chat_id, HURGHADA["brief"])

    body = client.post("/api/memory", json={"history": [chat_id], "forget": ["visa"]}).json()

    keys = {f["key"] for f in body["facts"]}
    assert "party" in keys and "visa" not in keys and f"trip:{chat_id}" in keys
    assert len(body["ideas"]) == 3
    assert client.post("/api/memory", json={"history": []}).json()["facts"] == []


async def _save_brief(sessionmaker, chat_id: str, brief: dict) -> None:
    async with sessionmaker() as db:
        await repository.save_brief(db, chat_id, brief)
        await db.commit()
