import json
from uuid import uuid4

from app.chats import repository


def create_chat(client, query: str) -> str:
    response = client.post("/api/chat/stream", json={"query": query})
    done = json.loads(response.text.strip().splitlines()[-1])
    return done["chat_id"]


def test_should_return_empty_list_without_ids(client):
    assert client.get("/api/chats?ids=").json() == {"items": []}


def test_should_list_only_existing_valid_chats_newest_first(client):
    first = create_chat(client, "Первый")
    second = create_chat(client, "Второй")

    ids = ",".join([first, "not-a-uuid", str(uuid4()), second])
    items = client.get(f"/api/chats?ids={ids}").json()["items"]

    assert [item["id"] for item in items] == [second, first]


def test_should_return_400_for_invalid_chat_id(client):
    assert client.get("/api/chats/not-a-uuid").status_code == 400


def test_should_return_404_for_unknown_chat(client):
    assert client.get(f"/api/chats/{uuid4()}").status_code == 404


def test_should_return_empty_messages_for_unknown_chat(client):
    assert client.get(f"/api/chats/{uuid4()}/messages").json() == {"messages": []}


def test_should_delete_chat_with_its_messages(client):
    chat_id = create_chat(client, "Удалить меня")

    assert client.delete(f"/api/chats/{chat_id}").status_code == 204
    assert client.get(f"/api/chats/{chat_id}").status_code == 404
    assert client.get(f"/api/chats/{chat_id}/messages").json() == {"messages": []}


def test_should_return_404_when_deleting_unknown_chat(client):
    assert client.delete(f"/api/chats/{uuid4()}").status_code == 404


def test_should_describe_each_trip_in_the_list(client):
    chat_id = create_chat(client, "Казань на выходные")
    brief = {"destination": "Казань", "month": 1, "nights_min": 2, "priced_from": "NQZ"}
    client.portal.call(_save_brief, client.app.state.sessionmaker, chat_id, brief)

    [item] = client.get(f"/api/chats?ids={chat_id}").json()["items"]

    assert item["summary"][:2] == ["Казань", "Январь · 2 ночи"]
    assert item["departure"] == "из Астаны"
    assert item["priced_at"] is None and item["stale"] is False and item["dates_passed"] is False


def test_should_send_the_trip_status_with_the_finished_reply(client):
    response = client.post("/api/chat/stream", json={"query": "Хочу к морю"})
    done = json.loads(response.text.strip().splitlines()[-1])

    assert done["summary"] == [] and done["stale"] is False


def test_should_refuse_to_refresh_a_trip_without_cards(client):
    chat_id = create_chat(client, "Пока без вариантов")

    assert client.post(f"/api/chats/{chat_id}/refresh").status_code == 409
    assert client.post(f"/api/chats/{uuid4()}/refresh").status_code == 404
    assert client.post("/api/chats/not-a-uuid/refresh").status_code == 400


async def _save_brief(sessionmaker, chat_id: str, brief: dict) -> None:
    async with sessionmaker() as db:
        await repository.save_brief(db, chat_id, brief)
        await db.commit()
