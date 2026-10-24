from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from tests.conftest import FakeLLM


def test_should_return_ok_on_health(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_should_serve_index_on_root(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "1surak app" in response.text


def test_should_fall_back_to_index_for_client_routes(client):
    response = client.get("/chat/some-id")

    assert response.status_code == 200
    assert "1surak app" in response.text


def test_should_serve_static_asset(client):
    response = client.get("/assets/app.js")

    assert response.status_code == 200
    assert "console.log" in response.text


def test_should_not_serve_files_outside_static_dir(client):
    response = client.get("/%2e%2e/secret.txt")

    assert "top-secret" not in response.text


def test_should_fall_back_to_index_for_a_null_byte_path(client):
    response = client.get("/assets/app.js%00.png")

    assert response.status_code == 200
    assert "1surak app" in response.text


def test_should_return_json_404_for_unknown_api_route(client):
    response = client.get("/api/does-not-exist")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")


def test_should_return_404_on_root_when_ui_is_not_built(tmp_path):
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'db.sqlite'}",
        static_dir=str(tmp_path / "missing"),
    )
    with TestClient(create_app(settings, llm=FakeLLM())) as test_client:
        assert test_client.get("/").status_code == 404
        assert test_client.get("/health").status_code == 200
