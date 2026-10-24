import json
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import FakeLLM


def stream_events(client, body: dict) -> list[dict]:
    response = client.post("/api/chat/stream", json=body)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-ndjson")
    return [json.loads(line) for line in response.text.splitlines() if line.strip()]


def test_should_stream_tokens_inside_a_visible_agent_step_then_done(client):
    events = stream_events(client, {"query": "Привет"})

    assert [e["type"] for e in events] == [
        "tool_start",
        "assistant_token",
        "assistant_token",
        "tool_end",
        "done",
    ]
    assert events[0]["title"] and events[0]["name"] == events[3]["name"]
    assert "".join(e["text"] for e in events if e["type"] == "assistant_token") == "Привет"
    done = events[-1]
    assert done["answer"] == "Привет"
    assert UUID(done["chat_id"])
    assert done["title"] == "Привет"


def test_should_persist_user_and_assistant_messages_with_agent_steps(client):
    done = stream_events(client, {"query": "Хочу к морю"})[-1]

    messages = client.get(f"/api/chats/{done['chat_id']}/messages").json()["messages"]

    assert [(m["role"], m["content"]) for m in messages] == [
        ("user", "Хочу к морю"),
        ("assistant", "Привет"),
    ]
    assert [step["type"] for step in messages[1]["trace"]] == ["tool_start", "tool_end"]


def test_should_send_previous_turns_to_llm_when_chat_continues(client, fake_llm):
    chat_id = str(uuid4())
    stream_events(client, {"query": "Первый вопрос", "chat_id": chat_id})
    stream_events(client, {"query": "Второй вопрос", "chat_id": chat_id})

    second_call = fake_llm.calls[1]
    turns = [(m["role"], m["content"]) for m in second_call if m["role"] != "system"]
    assert turns == [
        ("user", "Первый вопрос"),
        ("assistant", "Привет"),
        ("user", "Второй вопрос"),
    ]


def test_should_keep_title_from_first_message(client):
    chat_id = str(uuid4())
    stream_events(client, {"query": "Первый вопрос", "chat_id": chat_id})
    stream_events(client, {"query": "Второй вопрос", "chat_id": chat_id})

    assert client.get(f"/api/chats/{chat_id}").json()["title"] == "Первый вопрос"


def test_should_truncate_long_title(client):
    done = stream_events(client, {"query": "а" * 200})[-1]

    assert len(done["title"]) <= 60


def test_should_strip_query_whitespace(client):
    done = stream_events(client, {"query": "  Казань  "})[-1]

    assert done["title"] == "Казань"


def test_should_reject_blank_query(client):
    assert client.post("/api/chat/stream", json={"query": "   "}).status_code == 422


def test_should_reject_too_long_query(client):
    assert client.post("/api/chat/stream", json={"query": "а" * 12_001}).status_code == 422


def test_should_reject_invalid_chat_id(client):
    response = client.post("/api/chat/stream", json={"query": "Привет", "chat_id": "nope"})

    assert response.status_code == 422


def test_should_emit_error_and_done_without_leaking_details_when_llm_fails(settings):
    llm = FakeLLM(chunks=["Частично"], error=RuntimeError("provider secret detail"))
    with TestClient(create_app(settings, llm=llm)) as test_client:
        events = stream_events(test_client, {"query": "Привет"})

    types = [e["type"] for e in events]
    assert "error" in types
    assert types[-1] == "done"
    assert types.count("tool_start") == types.count("tool_end")
    assert "provider secret detail" not in json.dumps(events, ensure_ascii=False)
