import asyncio
import os
from collections.abc import AsyncIterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url

from app.config import Settings
from app.db import reset_database
from app.flights import RouteFlights, Ticket
from app.fx import FixedRates
from app.fx import configure as configure_rates
from app.ground import NoGround
from app.ground import configure as configure_ground
from app.llm import LLMEvent, TextDelta, ToolCall
from app.main import create_app
from app.plan.live_guide import SeedGuides
from app.plan.live_guide import configure as configure_guides
from app.plan.taxi import NoTaxiFares
from app.plan.taxi import configure as configure_taxi
from app.visas import NoFees
from app.visas import configure as configure_fees


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
        self.tool_choices: list[str | None] = []

    async def stream(
        self, messages: list[dict], tools: list[dict] | None = None, tool_choice: str | None = None
    ) -> AsyncIterator[LLMEvent]:
        self.tool_choices.append(tool_choice)
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


TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL", "postgresql+asyncpg://onesurak:onesurak@127.0.0.1:5433/onesurak_test"
)


def fresh_database(suffix: str = "") -> str:
    """An emptied test database; module-scoped fixtures pass a suffix so per-test cleanup can't touch theirs."""
    url = make_url(TEST_DATABASE_URL)
    if suffix:
        url = url.set(database=f"{url.database}_{suffix}")
    rendered = url.render_as_string(hide_password=False)
    asyncio.run(reset_database(rendered))
    return rendered


@pytest.fixture
def db_url() -> str:
    return fresh_database()


def route(minutes: int, direct: bool = True, price: int = 20_000, airline: str = "SU") -> RouteFlights:
    """Real-looking tickets for one route: a direct flight, or one with a transfer."""
    ticket = Ticket(
        "XXX", "YYY", airline, "100", "2026-11-13T05:05:00+03:00", price, 0 if direct else 1, minutes, "/s"
    )
    return RouteFlights(cheapest=ticket, direct=ticket if direct else None, fastest=ticket)


class FakeFlights:
    """Flights by destination IATA; routes not listed have no tickets."""

    def __init__(self, table: dict[str, RouteFlights] | None = None):
        self.table = table or {}
        self.asked: list[tuple[str, str, int | None]] = []

    async def route(self, origin: str, destination: str, month: int | None = None) -> RouteFlights | None:
        self.asked.append((origin, destination, month))
        return self.table.get(destination)

    async def routes(self, origin: str, destinations: list[str], month: int | None) -> dict:
        return {d: await self.route(origin, d, month) for d in destinations}


@pytest.fixture(autouse=True)
def no_real_ground():
    """An app built in a test switches real trains and buses on (the default); none may leak into the next test."""
    configure_ground(NoGround())
    yield
    configure_ground(NoGround())


@pytest.fixture(autouse=True)
def no_real_web_lookups():
    """An app with a model and web search looks visa fees and taxi fares up on the web, and exchange rates
    online; no test may leave that switched on."""
    configure_fees(NoFees())
    configure_taxi(NoTaxiFares())
    configure_rates(FixedRates())
    configure_guides(SeedGuides())
    yield
    configure_fees(NoFees())
    configure_taxi(NoTaxiFares())
    configure_rates(FixedRates())
    configure_guides(SeedGuides())


@pytest.fixture
def static_dir(tmp_path):
    static = tmp_path / "static"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text("<html>1surak app</html>", encoding="utf-8")
    (static / "assets" / "app.js").write_text("console.log('1surak')", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("top-secret", encoding="utf-8")
    return static


@pytest.fixture
def settings(db_url, static_dir):
    return Settings(
        database_url=db_url,
        static_dir=str(static_dir),
        llm_api_key="",
        seed_catalog=False,
        embeddings=False,
        destination_climate=False,  # no Open-Meteo calls from tests
        ground_transport=False,  # no test calls a real timetable
        live_rates=False,  # nor the exchange rates
        live_guides=False,  # nor Wikidata and OpenStreetMap
        osm_hotels=False,  # nor Nominatim
    )


@pytest.fixture
def fake_llm():
    return FakeLLM()


@pytest.fixture
def client(settings, fake_llm):
    with TestClient(create_app(settings, llm=fake_llm)) as test_client:
        yield test_client
