"""Text embeddings for the knowledge base: a small multilingual model that runs on the CPU, no API key.
Search uses them next to word matching; if the model can't load, search simply runs on words alone."""

import logging
import math
import os
import threading
from typing import Protocol

import anyio

log = logging.getLogger(__name__)

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DIMENSIONS = 384
SEMANTIC_MATCH = 0.45  # on the seed, passages that answer score 0.47-0.52 and unrelated ones 0.19-0.39
MEANING_FLOOR = 0.3  # below this a passage isn't "found by meaning" at all, so it gets no ranking boost


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class FastEmbedder:
    """Loads the model on first use, so an app that never searches by meaning never pays for it."""

    def __init__(self, cache_dir: str | None = None):
        self._cache_dir = cache_dir or os.getenv("FASTEMBED_CACHE_DIR")
        self._model = None
        self._error: Exception | None = None  # a model that failed to load stays failed until restart
        self._lock = threading.Lock()

    def embed(self, texts: list[str]) -> list[list[float]]:
        with self._lock:
            if self._error is not None:
                raise self._error
            if self._model is None:
                from fastembed import TextEmbedding

                try:
                    self._model = TextEmbedding(MODEL_NAME, cache_dir=self._cache_dir)
                except Exception as error:
                    self._error = error
                    raise
        # shortcut: the model reads only the first 128 tokens of a passage; embed windows if evals miss
        return [vector.tolist() for vector in self._model.embed(texts)]


async def embed_or_none(embedder: Embedder | None, texts: list[str]) -> list[list[float]] | None:
    """Vectors computed off the event loop, or None so the caller falls back to word search."""
    if embedder is None or not texts:
        return None
    try:
        return await anyio.to_thread.run_sync(embedder.embed, texts)
    except Exception:
        log.exception("Embedding failed, searching by words only")
        return None


def cosine(a: list[float], b: list[float]) -> float:
    norms = math.hypot(*a) * math.hypot(*b)
    return sum(x * y for x, y in zip(a, b, strict=True)) / norms if norms else 0.0
