from collections.abc import AsyncIterator

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.llm import LLMEvent, TextDelta, ToolCall
from app.main import create_app


class FakeLLM:
    """Scripted model. `chunks` is the text reply for every call; `rounds` scripts one reply per call,
    where a str is streamed text and a ToolCall is a tool request."""

    def __init__(
        self,
        chunks: list[str] | None = None,
        error: Exception | None = None,
        rounds: list[list[str | ToolCall]] | None = None,
    ):
        self.chunks = chunks if chunks is not None else ["При", "вет"]
        self.error = error
        self.rounds = list(rounds) if rounds is not None else None
        self.calls: list[list[dict]] = []  # exactly what the model saw
        self.conversations: list[list[dict]] = []  # the same without the reminders appended at the end
        self.tools_seen: list[list[dict] | None] = []

    async def stream(self, messages: list[dict], tools: list[dict] | None = None) -> AsyncIterator[LLMEvent]:
        seen = [dict(m) for m in messages]
        self.calls.append(seen)
        end = len(seen)
        while end > 1 and seen[end - 1]["role"] == "system":
            end -= 1
        self.conversations.append(seen[:end])
        self.tools_seen.append(tools)
        script = self.rounds.pop(0) if self.rounds else self.chunks
        for item in script:
            yield TextDelta(item) if isinstance(item, str) else item
        if self.error:
            raise self.error


@pytest.fixture
def static_dir(tmp_path):
    static = tmp_path / "static"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text("<html>1surak app</html>", encoding="utf-8")
    (static / "assets" / "app.js").write_text("console.log('1surak')", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("top-secret", encoding="utf-8")
    return static


@pytest.fixture
def settings(tmp_path, static_dir):
    return Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        static_dir=str(static_dir),
        llm_api_key="",
        seed_catalog=False,
    )


@pytest.fixture
def fake_llm():
    return FakeLLM()


@pytest.fixture
def client(settings, fake_llm):
    with TestClient(create_app(settings, llm=fake_llm)) as test_client:
        yield test_client
