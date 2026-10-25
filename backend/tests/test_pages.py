"""Brave search, read_page (download, extraction, quote check, saving) and the token-saving helpers."""

import asyncio
import json
from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
import pytest
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.catalog.catalog import load_catalog
from app.config import Settings
from app.db import init_db
from app.kb import page as page_module
from app.kb import repository
from app.kb.page import Extractor, Page, PageError, PageReader, PageTools
from app.kb.text import excerpt, sections
from app.kb.tools import ReadPageArgs, read_page_handler, read_page_preview
from app.kb.web import BraveSearch, FallbackSearch, TavilySearch, WebResult, build_web_search
from app.tools.registry import Tool, ToolRegistry, compact_schema

NOW = datetime(2026, 10, 25, 12, tzinfo=UTC)


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def db(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'kb.db'}")
    asyncio.run(init_db(engine))
    yield async_sessionmaker(engine, expire_on_commit=False)
    asyncio.run(engine.dispose())


@pytest.fixture
def public_dns(monkeypatch):
    """Every host resolves to a public address, unless the test maps it elsewhere."""
    addresses = {}

    async def getaddrinfo(host, port, *args, **kwargs):
        return [(2, 1, 6, "", (addresses.get(host, "93.184.216.34"), port))]

    monkeypatch.setattr(page_module.anyio, "getaddrinfo", getaddrinfo)
    return addresses


# --- token savers --------------------------------------------------------------------------------------


class Args(BaseModel):
    month: int | None = Field(None, ge=1, le=12, description="Travel month.")
    title: str = Field(description="A field named title stays.")
    kinds: list[str] | None = None


def test_should_drop_titles_and_null_variants_from_tool_schemas_but_keep_required_fields():
    schema = compact_schema(Args.model_json_schema())

    assert "title" not in schema
    assert schema["properties"]["month"] == {
        "type": "integer",
        "minimum": 1,
        "maximum": 12,
        "description": "Travel month.",
    }
    assert schema["properties"]["kinds"] == {"type": "array", "items": {"type": "string"}}
    assert schema["properties"]["title"]["description"] == "A field named title stays."
    assert schema["required"] == ["title"]


def test_should_send_compact_json_without_empty_fields_to_the_model():
    async def handler(_):
        return {"a": None, "b": [{"c": None, "d": 1}], "e": "ж"}

    class NoArgs(BaseModel):
        pass

    tool = Tool(name="t", title="t", description="d", args=NoArgs, handler=handler)
    result = run(ToolRegistry([tool]).execute("t", "{}"))

    assert result.content == '{"b":[{"d":1}],"e":"ж"}'


def test_should_keep_only_the_sentences_about_the_question():
    text = "Город стоит на реке. " * 20 + "Виза для россиян не нужна до 30 дней. " + "Много музеев. " * 20

    short = excerpt(text, "Нужна ли виза?", 200)

    assert "Виза для россиян не нужна до 30 дней." in short
    assert len(short) <= 200 and short.startswith("…")


def test_should_bring_a_matching_heading_with_its_section():
    text = "\n".join(
        ["Вступление про город."] * 50 + ["Еда", "Попробуйте чак-чак и эчпочмак."] + ["Музеи."] * 50
    )

    part = sections(text, "Что поесть, какая еда?", 300)

    assert "Еда\nПопробуйте чак-чак и эчпочмак." in part


# --- Brave ---------------------------------------------------------------------------------------------


def test_should_turn_brave_llm_context_into_dated_results_without_otas():
    seen = {}

    def reply(request: httpx.Request) -> httpx.Response:
        seen["params"] = dict(request.url.params)
        seen["key"] = request.headers["x-subscription-token"]
        return httpx.Response(
            200,
            json={
                "grounding": {
                    "generic": [
                        {
                            "url": "https://visa.gov.example/tdac",
                            "title": "TDAC",
                            "snippets": ["Нужна", "для всех"],
                        },
                        {"url": "https://www.booking.com/x", "title": "OTA", "snippets": ["hotel"]},
                        {"url": "https://empty.example", "title": "Empty", "snippets": []},
                    ]
                },
                "sources": {
                    "https://visa.gov.example/tdac": {"age": ["Monday", "2026-05-01", "5 months ago", "x"]}
                },
            },
        )

    brave = BraveSearch("key", transport=httpx.MockTransport(reply))
    results = run(brave.search("TDAC на ребёнка"))

    assert results == [
        WebResult(
            url="https://visa.gov.example/tdac",
            title="TDAC",
            content="Нужна для всех",
            published="2026-05-01",
        )
    ]
    assert seen["key"] == "key"
    assert seen["params"]["search_lang"] == "ru"
    assert "$discard,site=booking.com" in seen["params"]["goggles"]


class FakeWeb:
    def __init__(self, results=None, error=None):
        self.results, self.error = results or [], error

    async def search(self, query):
        if self.error:
            raise self.error
        return self.results


def test_should_try_the_next_search_when_one_finds_nothing():
    found = [WebResult(url="https://a.example", title="A", content="x")]

    assert run(FallbackSearch([FakeWeb([]), FakeWeb(found)]).search("q")) == found
    assert run(FallbackSearch([FakeWeb(error=RuntimeError("429")), FakeWeb([])]).search("q")) == []


def test_should_put_brave_first_when_it_has_a_key():
    chain = build_web_search("auto", "", 5.0, brave_key="k")
    assert [type(s) for s in chain._searches] == [BraveSearch, TavilySearch]
    assert isinstance(build_web_search("auto", "", 5.0), TavilySearch)
    tavily_first = build_web_search("tavily", "", 5.0, brave_key="k")
    assert [type(s) for s in tavily_first._searches] == [TavilySearch, BraveSearch]


def test_should_read_the_brave_key_from_either_env_name(monkeypatch):
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "abc")
    assert Settings(_env_file=None).brave_api_key == "abc"


# --- page reader ---------------------------------------------------------------------------------------

HTML = (
    "<html><head><title>Entry rules</title></head><body><article><h1>Entry rules</h1>"
    + "<p>Travellers need a passport valid for six months after arrival. Children need their own passport.</p>"
    + "".join(
        f"<p>Rule {i}: keep a printed copy of the hotel booking number {i} for border control.</p>"
        for i in range(8)
    )
    + "</article></body></html>"
)


def test_should_refuse_private_addresses_and_booking_sites(public_dns):
    public_dns["intranet.example"] = "10.0.0.5"
    reader = PageReader()

    for url in [
        "http://127.0.0.1:8080/api",
        "http://intranet.example/",
        "https://booking.com/x",
        "file:///etc/passwd",
    ]:
        with pytest.raises(PageError):
            run(reader.read(url))


def test_should_refuse_a_redirect_to_a_private_address(public_dns):
    public_dns["internal.example"] = "192.168.1.1"

    def reply(request):
        return httpx.Response(302, headers={"location": "http://internal.example/admin"})

    reader = PageReader(transport=httpx.MockTransport(reply))
    with pytest.raises(PageError):
        run(reader.read("https://public.example/"))


def test_should_extract_the_main_text_and_cache_the_page(public_dns):
    calls = []

    def reply(request):
        calls.append(str(request.url))
        return httpx.Response(200, html=HTML)

    reader = PageReader(transport=httpx.MockTransport(reply))
    page = run(reader.read("https://gov.example/entry"))
    again = run(reader.read("https://gov.example/entry"))

    assert "passport valid for six months" in page.text
    assert page.title == "Entry rules"
    assert again is page and len(calls) == 1


def test_should_use_jina_reader_when_the_html_has_no_text(public_dns):
    def reply(request):
        if request.url.host == "r.jina.ai":
            content = "Rendered by Jina. " * 40
            return httpx.Response(200, json={"data": {"title": "App", "content": content}})
        return httpx.Response(200, html="<html><body><div id='app'></div></body></html>")

    page = run(PageReader(transport=httpx.MockTransport(reply)).read("https://spa.example/"))

    assert page.title == "App" and page.text.startswith("Rendered by Jina.")


# --- extraction and the tool ---------------------------------------------------------------------------


class FakeCompletions:
    def __init__(self, answer: dict):
        self.answer = answer
        self.kwargs = None

    async def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(self.answer)))],
            usage=SimpleNamespace(prompt_tokens=900, completion_tokens=80),
        )


def extractor_answering(answer: dict) -> tuple[Extractor, FakeCompletions]:
    completions = FakeCompletions(answer)
    return Extractor(SimpleNamespace(chat=SimpleNamespace(completions=completions)), "mini"), completions


PAGE = Page(
    url="https://gov.example/entry",
    title="Entry rules",
    text="Travellers need a passport valid for six months after arrival.\nChildren need their own passport.",
)


def test_should_keep_only_facts_whose_quote_is_on_the_page():
    extractor, completions = extractor_answering(
        {
            "found": True,
            "facts": [
                {
                    "fact": "Паспорт должен действовать 6 месяцев",
                    "quote": "passport  valid for six months after",
                },
                {"fact": "Виза не нужна", "quote": "No visa is required for anyone."},
            ],
            "published": None,
        }
    )

    found = run(extractor.extract("Какой нужен паспорт?", PAGE))

    assert [f["fact"] for f in found.facts] == ["Паспорт должен действовать 6 месяцев"]
    assert found.dropped == 1
    assert completions.kwargs["response_format"]["json_schema"]["strict"] is True
    assert extractor.input_tokens == 900


def test_should_return_no_facts_when_the_model_says_the_page_has_no_answer():
    extractor, _ = extractor_answering(
        {
            "found": False,
            "facts": [{"fact": "Нет ответа", "quote": "Children need their own passport."}],
            "published": None,
        }
    )

    assert run(extractor.extract("Сколько стоит виза?", PAGE)).facts == []


class FakeReader:
    def __init__(self, page=None, error=None):
        self.page, self.error = page, error

    async def read(self, url):
        if self.error:
            raise self.error
        return self.page


def test_should_save_checked_facts_to_the_base_with_their_source(db):
    extractor, _ = extractor_answering(
        {
            "found": True,
            "facts": [{"fact": "Детям нужен свой паспорт", "quote": "Children need their own passport."}],
            "published": "2026-09-01",
        }
    )
    handler = read_page_handler(db, load_catalog(), PageTools(FakeReader(PAGE), extractor), lambda: NOW)

    result = run(handler(ReadPageArgs(url=PAGE.url, question="Нужен ли ребёнку паспорт?", topic="visa")))

    assert result["facts"] == [
        {"fact": "Детям нужен свой паспорт", "quote": "Children need their own passport."}
    ]
    assert result["published"] == "2026-09-01" and result["checked"] == "2026-10-25"

    async def stored():
        async with db() as s:
            return await repository.search(s, "паспорт ребёнку", NOW)

    saved = run(stored())
    assert saved and saved[0].source_url == PAGE.url and saved[0].kind == "fact"
    assert "Прочитал gov.example: 1 фактов" in read_page_preview(result)


def test_should_report_a_page_it_cannot_read_and_fall_back_to_raw_text_without_a_model(db):
    failing = read_page_handler(db, load_catalog(), PageTools(FakeReader(error=PageError("blocked")), None))
    assert (
        run(failing(ReadPageArgs(url="https://x.example", question="q", topic="tip")))["error"] == "blocked"
    )

    raw = read_page_handler(db, load_catalog(), PageTools(FakeReader(PAGE), None), lambda: NOW)
    result = run(raw(ReadPageArgs(url=PAGE.url, question="Какой паспорт?", topic="visa")))
    assert "passport" in result["excerpt"]
