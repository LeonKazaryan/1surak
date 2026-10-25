"""The simulated checkout: the plan the agent showed plus the extras the user ticked becomes a booking."""

from uuid import uuid4

from app.chats import repository
from tests.test_chats import create_chat

EARLY = {
    "id": "early_check_in:antalya-h1",
    "type": "early_check_in",
    "label": "Ранний заезд в «Бриз»",
    "price_rub": 5_000,
}
LATE = {
    "id": "late_check_out:alanya-h2",
    "type": "late_check_out",
    "label": "Поздний выезд из «Маяк»",
    "price_rub": 3_000,
}
PLAN = {
    "type": "trip_plan",
    "id": "antalya",
    "name": "Анталья",
    "dates": {"from": "2026-11-06", "to": "2026-11-13", "nights": 7},
    "checks": [
        {"level": "warn", "title": "Прилёт 07:00, заселение с 14:00", "text": "…", "fix": EARLY},
        {"level": "ok", "title": "Выезд до 12:00, вылет 15:00", "text": "…", "fix": None},
    ],
    "costs": {"total": 200_000},
    "currency": {"code": "KZT", "sign": "₸", "glyph": "₸", "per_rub": 5.56},
}


async def _add(sessionmaker, chat_id: str, trace: list[dict]) -> str:
    async with sessionmaker() as db:
        saved = await repository.add_message(db, chat_id, "assistant", "Собрал поездку", trace)
        await db.commit()
    return saved["id"]


def planned(client, plans: int = 1) -> tuple[str, str]:
    chat_id = create_chat(client, "Анталья в ноябре")
    for n in range(plans):
        plan = {**PLAN, "costs": {"total": 200_000 + n * 10_000}}
        message_id = client.portal.call(_add, client.app.state.sessionmaker, chat_id, [plan])
    return chat_id, message_id


def book(client, chat_id: str, **body):
    payload = {"extras": [], "holder": "Анна Смирнова", **body}
    return client.post(f"/api/chats/{chat_id}/booking", json=payload)


def test_should_book_the_plan_with_the_extras_it_offers(client):
    chat_id, message_id = planned(client)

    response = book(client, chat_id, extras=["early_check_in:antalya-h1", "late_check_out:antalya-h1"])

    assert response.status_code == 200
    message = response.json()
    [booking] = message["trace"]
    assert booking["type"] == "booking" and booking["number"].startswith("1S-")
    assert booking["extras"] == [EARLY]  # late check-out was not offered by this plan
    assert booking["total_rub"] == 205_000 and booking["holder"] == "Анна Смирнова"
    assert booking["plan_message_id"] == message_id
    assert booking["currency"]["code"] == "KZT"
    assert "6–13 ноября" in message["content"]
    saved = client.get(f"/api/chats/{chat_id}/messages").json()["messages"]
    assert saved[-1]["id"] == message["id"]


def test_should_book_the_latest_plan_and_only_once(client):
    chat_id, latest = planned(client, plans=2)

    first = book(client, chat_id).json()
    again = book(client, chat_id).json()

    messages = client.get(f"/api/chats/{chat_id}/messages").json()["messages"]
    assert again["id"] == first["id"]
    assert first["trace"][0]["plan_message_id"] == latest and first["trace"][0]["total_rub"] == 210_000
    assert len(messages) == 5  # ask, reply, two plans, one booking


def test_should_refuse_a_trip_without_a_plan_or_a_name(client):
    chat_id, _ = planned(client)

    assert book(client, create_chat(client, "Пока без плана")).status_code == 404
    assert book(client, str(uuid4())).status_code == 404
    assert book(client, "not-a-uuid").status_code == 400
    assert book(client, chat_id, holder=" ").status_code == 422
    assert book(client, chat_id, extras=["free_spa"]).status_code == 422
    assert book(client, chat_id, extras=["early_check_in"]).status_code == 422


def test_should_not_book_a_trip_whose_dates_have_passed(client):
    chat_id = create_chat(client, "Анталья прошлой зимой")
    past = {**PLAN, "dates": {"from": "2025-01-10", "to": "2025-01-17", "nights": 7}}
    client.portal.call(_add, client.app.state.sessionmaker, chat_id, [past])

    response = book(client, chat_id)

    assert response.status_code == 409
    assert len(client.get(f"/api/chats/{chat_id}/messages").json()["messages"]) == 3


def test_should_charge_each_stops_extra_once_on_a_two_city_trip(client):
    chat_id = create_chat(client, "Анталья и Аланья")
    other = {**EARLY, "id": "early_check_in:alanya-h2", "label": "Ранний заезд в «Маяк»", "price_rub": 2_500}
    checks = [{"level": "warn", "title": "…", "text": "…", "fix": fix} for fix in (EARLY, other, LATE)]
    client.portal.call(_add, client.app.state.sessionmaker, chat_id, [{**PLAN, "checks": checks}])

    booking = book(client, chat_id, extras=[EARLY["id"], other["id"]]).json()["trace"][0]

    assert booking["extras"] == [EARLY, other]
    assert booking["total_rub"] == 200_000 + 5_000 + 2_500
