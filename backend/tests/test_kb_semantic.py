"""Hybrid knowledge base search: by words and by meaning. A fake embedder keeps most tests fast;
the last test runs the real model on pairs where word matching fails."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import Settings
from app.db import init_db, kb_entries
from app.kb import repository
from app.kb.embeddings import DIMENSIONS, MODEL_NAME, SEMANTIC_MATCH, FastEmbedder, cosine
from app.kb.seed import backfill_embeddings, seed_entries
from app.kb.tools import research_tool
from app.main import create_app
from tests.conftest import FakeLLM
from tests.test_kb import NOW, FakeWeb, call, entry, run, web_results

CONCEPTS = {
    "kids": ("ребён", "ребен", "дет", "семей", "kids"),
    "calm": ("тиш", "спокой", "quiet"),
    "sea": ("море", "пляж", "beach"),
    "visa": ("виз", "visa", "tdac"),
}


@pytest.fixture
def db(db_url):
    engine = create_async_engine(db_url, poolclass=NullPool)
    run(init_db(engine))
    yield async_sessionmaker(engine, expire_on_commit=False)
    run(engine.dispose())


class FakeEmbedder:
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.calls: list[list[str]] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self.fail:
            raise RuntimeError("model unavailable")
        self.calls.append(list(texts))
        return [self._vector(text) for text in texts]

    @staticmethod
    def _vector(text: str) -> list[float]:
        low = text.casefold()
        vector = [float(sum(low.count(stem) for stem in stems)) for stems in CONCEPTS.values()]
        vector += [0.0] * (DIMENSIONS - len(vector))
        if not any(vector):
            vector[-1] = 1.0  # unrelated text points somewhere else entirely
        return vector


async def _add_embedded(sessionmaker, embedder, entries) -> list[int]:
    async with sessionmaker() as s:
        ids = await repository.add_entries(s, entries, embedder.embed([e.text for e in entries]))
        await s.commit()
        return ids


async def _search(sessionmaker, embedder, query: str, **kw):
    async with sessionmaker() as s:
        return await repository.search(s, query, NOW, query_vector=embedder.embed([query])[0], **kw)


def test_should_find_a_passage_by_meaning_when_no_words_match(db):
    embedder = FakeEmbedder()
    kids, clubs = (
        entry("Отель подходит для семей с детьми", "hotel"),
        entry("Ночные клубы и бары до утра", "hotel"),
    )
    run(_add_embedded(db, embedder, [clubs, kids]))

    found = run(_search(db, embedder, "отдых с ребёнком", topics=["hotel"]))

    assert found[0].text == "Отель подходит для семей с детьми"
    assert found[0].similarity >= SEMANTIC_MATCH


def test_should_put_entries_found_by_both_searches_first():
    assert repository.fuse_rankings([1, 2, 3], [3, 4]) == [3, 1, 2, 4]


def test_should_not_let_a_word_match_ride_on_a_meaning_score_it_did_not_earn(db):
    embedder = FakeEmbedder()
    run(
        _add_embedded(
            db, embedder, [entry("Отдых в горах зимой", "tip"), entry("Отель для семей с детьми", "tip")]
        )
    )

    found = run(_search(db, embedder, "отдых с ребёнком", topics=["tip"]))

    assert [e.text for e in found] == ["Отель для семей с детьми", "Отдых в горах зимой"]
    assert found[1].similarity is None


def test_should_answer_from_the_base_when_a_stored_passage_is_close_in_meaning(db):
    embedder = FakeEmbedder()
    stored = entry("Отель подходит для семей с детьми", "hotel", place_id="hurghada")
    run(_add_embedded(db, embedder, [stored]))
    web = FakeWeb(web_results())

    result = call(
        research_tool(db, web, now=lambda: NOW, embedder=embedder),
        question="Где остановиться с ребёнком?",
        topic="hotel",
        place="hurghada",
    )

    assert result["answered_from"] == "база знаний" and web.queries == []


def test_should_still_search_the_web_when_nothing_stored_is_close_in_meaning(db):
    embedder = FakeEmbedder()
    run(_add_embedded(db, embedder, [entry("Ночные клубы и бары до утра", "hotel", place_id="hurghada")]))
    web = FakeWeb(web_results())

    result = call(
        research_tool(db, web, now=lambda: NOW, embedder=embedder),
        question="Где остановиться с ребёнком?",
        topic="hotel",
        place="hurghada",
    )

    assert result["answered_from"] == "интернет"
    assert embedder.calls[-1] == [p["text"] for p in result["passages"]]  # web finds are embedded too


def test_should_fall_back_to_word_search_when_the_model_fails(db):
    run(
        _add_embedded(
            db, FakeEmbedder(), [entry("Снорклинг у рифа с пологим входом", "tip", place_id="hurghada")]
        )
    )
    web = FakeWeb(web_results())

    result = call(
        research_tool(db, web, now=lambda: NOW, embedder=FakeEmbedder(fail=True)),
        question="где снорклинг с пологим входом?",
        topic="tip",
        place="hurghada",
    )

    assert result["answered_from"] == "база знаний" and web.queries == []


def test_should_embed_stored_entries_that_have_no_vector_yet(db):
    async def add_plain():
        async with db() as s:
            await repository.add_entries(
                s, [entry("Пляж с мелким входом", "tip"), entry("Виза не нужна", "visa")]
            )
            await s.commit()

    run(add_plain())
    embedder = FakeEmbedder()

    assert run(backfill_embeddings(db, embedder)) == 2
    assert run(backfill_embeddings(db, embedder)) == 0
    assert run(_search(db, embedder, "дети на пляже"))[0].text == "Пляж с мелким входом"


def test_should_embed_again_what_an_older_model_embedded(db):
    embedder = FakeEmbedder()
    run(_add_embedded(db, embedder, [entry("Пляж с мелким входом", "tip")]))

    async def mark_old():
        async with db() as s:
            await s.execute(update(kb_entries).values(embedding_model="old-model"))
            await s.commit()

    run(mark_old())

    assert run(backfill_embeddings(db, embedder)) == 1
    assert run(backfill_embeddings(db, embedder)) == 0


def test_should_try_to_load_a_missing_model_only_once(monkeypatch):
    loads = []

    def broken_model(*args, **kwargs):
        loads.append(args)
        raise OSError("no model files offline")

    monkeypatch.setattr("fastembed.TextEmbedding", broken_model)
    embedder = FastEmbedder()

    for _ in range(2):
        with pytest.raises(OSError):
            embedder.embed(["море"])

    assert len(loads) == 1


def test_should_bake_the_app_model_and_fastembed_version_into_the_image():
    backend = Path(__file__).parents[1]
    dockerfile = (backend.parent / "Dockerfile").read_text()
    requirements = (backend / "requirements.txt").read_text().splitlines()
    pin = next(line for line in requirements if line.startswith("fastembed=="))

    assert MODEL_NAME in dockerfile and pin in dockerfile


PAIRS = [
    ("отдых с ребёнком", "Отель подходит для семей с детьми", True),
    ("тишина и природа", "Спокойный отдых вдали от города", True),
    ("море", "Тёплое море и песчаные пляжи", True),
    ("quiet beach for kids", "Спокойный пляж с пологим входом, удобно с детьми", True),
    ("море", "Зимой тут мороз до -30", False),
    ("виза в Таиланд", "Пляжи Пхукета и ночная жизнь Патонга", False),
    ("отдых с ребёнком", "Ночные клубы и бары до утра", False),
]


@pytest.fixture(scope="module")
def model():
    return FastEmbedder()


@pytest.mark.parametrize(("question", "passage", "close"), PAIRS)
def test_should_tell_close_meaning_from_shared_letters_with_the_real_model(model, question, passage, close):
    a, b = model.embed([question, passage])

    assert (cosine(a, b) >= SEMANTIC_MATCH) is close


def test_should_embed_the_knowledge_base_seed_when_the_app_starts(db_url, static_dir):
    settings = Settings(database_url=db_url, static_dir=str(static_dir), llm_api_key="")
    embedder = FakeEmbedder()

    with TestClient(create_app(settings, llm=FakeLLM(), embedder=embedder)):
        pass

    assert len(embedder.calls[0]) == len(seed_entries())
