import json
from uuid import uuid4


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
