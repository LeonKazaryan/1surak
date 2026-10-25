import asyncio
import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db import init_db
from app.kb import repository
from app.kb.model import Entry, source_tier
from app.kb.research import ResearchArgs, research_preview
from app.kb.seed import load_kb_seed
from app.kb.text import coverage, fts_query, terms
from app.kb.tools import research_tool
from app.kb.web import WebResult

NOW = datetime(2026, 10, 25, 12, tzinfo=UTC)


class FakeWeb:
    def __init__(self, results: list[WebResult] | None = None, error: Exception | None = None):
        self.results = results or []
        self.error = error
        self.queries: list[str] = []

    async def search(self, query: str) -> list[WebResult]:
        self.queries.append(query)
        if self.error:
            raise self.error
        return self.results


def entry(text: str, topic="visa", url="https://example.com/a", **kw) -> Entry:
    return Entry(text=text, topic=topic, source_url=url, fetched_at=kw.pop("fetched_at", NOW), **kw)


@pytest.fixture
def db(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'kb.db'}")
    asyncio.run(init_db(engine))
    yield async_sessionmaker(engine, expire_on_commit=False)
    asyncio.run(engine.dispose())


def run(coro):
    return asyncio.run(coro)


async def _add(sessionmaker, entries: list[Entry]) -> list[int]:
    async with sessionmaker() as s:
        ids = await repository.add_entries(s, entries)
        await s.commit()
        return ids


async def _search(sessionmaker, query: str, **kw) -> list[Entry]:
    async with sessionmaker() as s:
        return await repository.search(s, query, kw.pop("now", NOW), **kw)


# --- text


def test_should_turn_russian_word_forms_into_shared_prefixes():
    assert terms("визы в Таиланд для россиян") == ["виз", "таил", "росс"]
    assert terms("отдых с детьми") == ["отд", "дет"]
    assert fts_query("и в на") is None


def test_should_measure_how_much_of_the_question_a_text_covers():
    assert coverage("виза в Таиланд", "Въезд в Таиланд без визы до 60 дней") == 1.0
    assert coverage("виза в Таиланд", "Пляжи Пхукета") == 0.0


# --- model


def test_should_refuse_an_entry_without_a_source_or_with_an_unknown_topic():
    with pytest.raises(ValueError, match="no source"):
        entry("текст", url="")
    with pytest.raises(ValueError, match="topic"):
        entry("текст", topic="gossip")


def test_should_rate_sources_and_set_freshness_by_topic():
    assert source_tier("https://www.mid.ru/ru/") == "official"
    assert source_tier("https://tdac.immigration.go.th/") == "official"
    assert source_tier("https://www.rbc.ru/travel/") == "media"
    assert source_tier("https://someblog.ru/post") == "community"
    assert entry("x", topic="visa").valid_until == NOW + timedelta(days=30)
    assert entry("x", topic="guide").valid_until == NOW + timedelta(days=180)
    assert entry("x", url="https://www.mid.ru/a").confidence == "verified"


def test_should_strip_markdown_and_cap_web_text():
    e = entry("## Заголовок ![img](http://x/i.png) [ссылка](http://x) " + "а" * 3000)
    assert e.text.startswith("Заголовок ссылка")
    assert len(e.text) == 1500


# --- repository


def test_should_find_other_word_forms_and_skip_duplicates(db):
    first = run(_add(db, [entry("Россиянам виза в Таиланд не нужна до 60 дней", country="TH")]))
    again = run(_add(db, [entry("Россиянам  виза в Таиланд не нужна до 60 дней!", country="TH")]))

    assert first == again
    assert [e.id for e in run(_search(db, "визы Таиланда"))] == first


def test_should_filter_by_place_keeping_country_wide_entries(db):
    run(
        _add(
            db,
            [
                entry("Виза в Египет по прибытии стоит 25 долларов", country="EG"),
                entry(
                    "В Хургаде виза ставится в аэропорту",
                    place_id="hurghada",
                    country="EG",
                    url="https://e.com/1",
                ),
                entry(
                    "В Шарм-эш-Шейхе действует синайский штамп, виза",
                    place_id="sharm",
                    country="EG",
                    url="https://e.com/2",
                ),
            ],
        )
    )

    found = run(_search(db, "виза", place_id="hurghada", country="EG"))

    assert {e.place_id for e in found} == {None, "hurghada"}


def test_should_hide_expired_entries_unless_asked(db):
    run(_add(db, [entry("Виза в Таиланд не нужна", fetched_at=NOW - timedelta(days=40))]))

    assert run(_search(db, "виза Таиланд")) == []
    assert len(run(_search(db, "виза Таиланд", fresh_only=False))) == 1


def test_should_filter_by_topic(db):
    run(
        _add(
            db,
            [
                entry("Чем заняться в Хургаде: снорклинг", topic="tip"),
                entry("Хургада виза", url="https://e.com/v"),
            ],
        )
    )

    assert [e.topic for e in run(_search(db, "Хургада", topics=["tip"]))] == ["tip"]


# --- research tool


def call(tool, **args) -> dict:
    return run(tool.handler(ResearchArgs(**args)))


def web_results() -> list[WebResult]:
    return [
        WebResult(
            "https://tdac.immigration.go.th/",
            "TDAC",
            "Карта прибытия TDAC в Таиланд обязательна для всех, в том числе для детей. Заполняют онлайн за 3 дня до прилёта.",
        ),
        WebResult(
            "https://someblog.ru/tdac",
            "Блог",
            "Как заполнить карту TDAC в Таиланд: пошаговая инструкция для россиян и детей.",
        ),
    ]


def test_should_search_the_web_on_a_miss_save_with_sources_then_answer_from_the_base(db):
    web = FakeWeb(web_results())
    tool = research_tool(db, web, now=lambda: NOW)

    first = call(tool, question="Нужна ли карта TDAC в Таиланд детям?", topic="visa", country="Таиланд")
    second = call(tool, question="Нужна ли карта TDAC в Таиланд детям?", topic="visa", country="TH")

    assert first["answered_from"] == "интернет" and first["saved_to_base"] == 2
    assert web.queries == ["Нужна ли карта TDAC в Таиланд детям?"]  # the country name is already in it
    official = first["passages"][0]
    assert official["tier"] == "official" and official["url"] == "https://tdac.immigration.go.th/"
    assert second["answered_from"] == "база знаний"
    assert len(web.queries) == 1
    assert research_preview(first).startswith("Поискал в интернете")
    assert research_preview(second).startswith("Нашёл в базе знаний")


def test_should_add_the_place_name_to_the_web_query(db):
    web = FakeWeb(web_results())
    tool = research_tool(db, web, now=lambda: NOW)

    call(tool, question="где хороший снорклинг с пологим входом?", topic="tip", place="hurghada")

    assert web.queries == ["где хороший снорклинг с пологим входом? Хургада"]


def test_should_trust_todays_entries_even_when_asked_for_fresh_data(db):
    web = FakeWeb(web_results())
    question = {"question": "карта TDAC Таиланд дети", "topic": "visa", "country": "TH"}

    call(research_tool(db, web, now=lambda: NOW), **question)
    call(research_tool(db, web, now=lambda: NOW + timedelta(hours=3)), **question, fresh=True)
    assert len(web.queries) == 1  # checked three hours ago is fresh enough

    call(research_tool(db, web, now=lambda: NOW + timedelta(days=2)), **question, fresh=True)
    assert len(web.queries) == 2


def test_should_resolve_english_country_names_and_keep_publication_apart_from_checking(db):
    web = FakeWeb(
        [WebResult("https://a.ru/x", "A", "Карта TDAC в Таиланд нужна детям", published="2026-05-01")]
    )

    result = call(
        research_tool(db, web, now=lambda: NOW), question="TDAC для детей", topic="visa", country="Thailand"
    )

    assert web.queries == ["TDAC для детей Таиланд"]
    passage = result["passages"][0]
    assert passage["published"] == "2026-05-01" and passage["checked"] == "2026-10-25"


def test_should_match_a_long_padded_question_against_a_stored_answer(db):
    run(
        _add(
            db,
            [
                entry(
                    "Карта прибытия TDAC в Таиланд обязательна, детям тоже",
                    country="TH",
                    url="https://a.ru/1",
                ),
                entry(
                    "Карту прибытия TDAC в Таиланд заполняют онлайн, на детей отдельно",
                    country="TH",
                    url="https://a.ru/2",
                ),
            ],
        )
    )
    web = FakeWeb(web_results())
    long_question = "Нужна ли россиянам электронная карта прибытия TDAC в Таиланд, где заполнять, с какой даты, кого касается?"

    result = call(research_tool(db, web, now=lambda: NOW), question=long_question, topic="visa", country="TH")

    assert result["answered_from"] == "база знаний" and web.queries == []


def test_should_fall_back_to_old_entries_with_a_warning_when_the_web_fails(db):
    run(
        _add(
            db, [entry("Карта TDAC в Таиланд нужна всем", country="TH", fetched_at=NOW - timedelta(days=60))]
        )
    )
    tool = research_tool(db, FakeWeb(error=RuntimeError("down")), now=lambda: NOW)

    result = call(tool, question="карта TDAC Таиланд", topic="visa", country="TH")

    assert result["answered_from"] == "база знаний (веб-поиск сейчас недоступен)"
    assert len(result["passages"]) == 1
    assert "устарела" in result["stale"]
    assert "перепроверить" in result["warning"]


def test_should_say_nothing_was_found_without_web_and_without_entries(db):
    result = call(research_tool(db, None, now=lambda: NOW), question="карнавал в Рио", topic="event")

    assert result["answered_from"] == "база знаний (веб-поиск выключен)"
    assert result["passages"] == [] and "нет ответа" in result["nothing_found"]


def test_should_load_the_seed_once(db, tmp_path):
    seed = tmp_path / "seed.json"
    seed.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "text": "Хургада. Чем заняться: снорклинг на рифах",
                        "topic": "tip",
                        "source_url": "https://ru.wikivoyage.org/w/index.php?title=X&oldid=1",
                        "place_id": "hurghada",
                        "fetched_at": NOW.isoformat(),
                        "valid_until": None,
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    assert run(load_kb_seed(db, seed)) is True
    assert run(load_kb_seed(db, seed)) is False
    found = run(_search(db, "снорклинг Хургада", place_id="hurghada"))
    assert found[0].created_by == "seed"


def test_should_not_count_the_place_name_as_an_answer(db):
    run(
        _add(
            db,
            [
                entry(
                    "Хургада. Чем заняться: дайвинг-центры и морские прогулки к островам",
                    topic="tip",
                    place_id="hurghada",
                    country="EG",
                    url="https://ru.wikivoyage.org/x",
                )
            ],
        )
    )
    web = FakeWeb(web_results())
    tool = research_tool(db, web, now=lambda: NOW)

    result = call(
        tool,
        question="Хургада: где пологий вход в море для ребёнка, какой район выбрать?",
        topic="tip",
        place="hurghada",
    )

    assert result["answered_from"] == "интернет"  # the stored passage only shared the name «Хургада»
    assert len(web.queries) == 1


# --- web providers


class Note:
    def __init__(self, url, start, end, title=None):
        self.type, self.url, self.start_index, self.end_index, self.title = (
            "url_citation",
            url,
            start,
            end,
            title,
        )


class FakeResponses:
    def __init__(self, text: str, notes: list[Note]):
        part = type("Part", (), {"text": text, "annotations": notes})()
        message = type("Msg", (), {"type": "message", "content": [part]})()
        self.output = [type("Call", (), {"type": "web_search_call"})(), message]
        self.kwargs = None

    async def create(self, **kwargs):
        self.kwargs = kwargs
        return self


def test_should_turn_openai_citations_into_sourced_results_without_tracking_or_otas():
    from types import SimpleNamespace

    from app.kb.web import OpenAIWebSearch

    text = "Вступление.\n> Крупную собаку везут в отдельном купе. (rzd.ru)\nЕщё абзац про booking."
    notes = [
        Note("https://pass.rzd.ru/pets?utm_source=openai&x=1", 13, 55, "РЖД"),
        Note("https://www.booking.com/x", 60, 80),
    ]
    responses = FakeResponses(text, notes)
    search = OpenAIWebSearch(SimpleNamespace(responses=responses), "gpt-test")

    results = run(search.search("собака в поезде"))

    assert [(r.url, r.title) for r in results] == [("https://pass.rzd.ru/pets?x=1", "РЖД")]
    assert results[0].content == "> Крупную собаку везут в отдельном купе. (rzd.ru)"
    assert responses.kwargs["tools"] == [{"type": "web_search"}] and responses.kwargs["model"] == "gpt-test"


def test_should_try_the_next_search_when_one_fails():
    from app.kb.web import FallbackSearch

    first, second = FakeWeb(error=RuntimeError("429")), FakeWeb(web_results())

    results = run(FallbackSearch([first, second]).search("TDAC"))

    assert len(results) == 2 and first.queries == second.queries == ["TDAC"]
    with pytest.raises(RuntimeError, match="429"):
        run(FallbackSearch([FakeWeb(error=RuntimeError("429"))]).search("TDAC"))


def test_should_add_openai_as_a_backup_only_when_the_agent_runs_on_openai():
    from types import SimpleNamespace

    from app.config import Settings
    from app.kb.web import FallbackSearch, TavilySearch, web_search_for
    from app.llm import OpenAICompatibleLLM, StubLLM

    llm = OpenAICompatibleLLM(client=SimpleNamespace(), model="m")
    assert isinstance(web_search_for(Settings(_env_file=None), llm), FallbackSearch)
    assert isinstance(
        web_search_for(Settings(_env_file=None, llm_base_url="https://openrouter.ai/api/v1"), llm),
        TavilySearch,
    )
    assert isinstance(web_search_for(Settings(_env_file=None), StubLLM()), TavilySearch)
    assert web_search_for(Settings(_env_file=None, search_provider="none"), llm) is None
