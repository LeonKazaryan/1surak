from collections.abc import AsyncIterator

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


class FakeLLM:
    def __init__(self, chunks: list[str] | None = None, error: Exception | None = None):
        self.chunks = chunks if chunks is not None else ["При", "вет"]
        self.error = error
        self.calls: list[list[dict]] = []

    async def stream(self, messages: list[dict]) -> AsyncIterator[str]:
        self.calls.append(messages)
        for chunk in self.chunks:
            yield chunk
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
    )


@pytest.fixture
def fake_llm():
    return FakeLLM()


@pytest.fixture
def client(settings, fake_llm):
    with TestClient(create_app(settings, llm=fake_llm)) as test_client:
        yield test_client
