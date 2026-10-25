"""One client cannot start more chat turns a minute than a person would; each turn spends LLM credits."""

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import create_app
from app.ratelimit import RateLimit


def test_should_refuse_the_request_over_the_limit_until_a_minute_passes():
    now = [0.0]
    limit = RateLimit(per_minute=2, clock=lambda: now[0])

    limit.hit("1.2.3.4")
    limit.hit("1.2.3.4")
    with pytest.raises(HTTPException) as refused:
        limit.hit("1.2.3.4")
    assert refused.value.status_code == 429
    assert refused.value.headers["Retry-After"] == "60"

    limit.hit("5.6.7.8")
    now[0] = 60.0
    limit.hit("1.2.3.4")


def test_should_let_every_request_through_when_the_limit_is_off():
    limit = RateLimit(per_minute=0)

    for _ in range(100):
        limit.hit("1.2.3.4")


def test_should_answer_429_on_the_chat_stream_over_the_limit(settings, fake_llm):
    limited = settings.model_copy(update={"rate_limit_per_minute": 1})

    with TestClient(create_app(limited, llm=fake_llm)) as client:
        assert client.post("/api/chat/stream", json={"query": "Море"}).status_code == 200
        assert client.post("/api/chat/stream", json={"query": "Море"}).status_code == 429
