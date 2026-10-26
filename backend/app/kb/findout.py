"""Finding one fact on the web: search, let a model read the excerpts, keep the answer only if its quote holds.

Shared by the visa fees and the taxi fares. The searches are tried in turn (the app's own, then the model's
web search), each with its queries in turn (English, then Russian), until the reader finds the answer; a search
that fails (a keyless rate limit) hands over to the next one. The model must quote the sentence its answer is
taken from, and the quote must be in the excerpt it names: a number the page does not say is not taken.
"""

import json
import logging
import re
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from app.kb.web import WebResult, WebSearch

log = logging.getLogger(__name__)

T = TypeVar("T")
MAX_EXCERPTS = 5
EXCERPT_CHARS = 1_500


def words(text: str) -> str:
    return " ".join(re.sub(r"[\W_]+", " ", text.casefold().replace("ё", "е")).split())


def digits(text: str) -> str:
    return re.sub(r"[\s  ,.']", "", text)


def quoted(quote: str, result: WebResult) -> bool:
    """The quote is really in this excerpt (spacing and punctuation aside)."""
    return bool(quote.strip()) and words(quote) in words(f"{result.title} {result.content}")


def says_amount(quote: str, amount: float) -> bool:
    """The quote has this number in it: «$185», «1 020 евро»."""
    return str(int(amount)) in digits(quote)


async def first_found(
    searches: list[WebSearch],
    queries: list[str],
    read: Callable[[list[WebResult]], Awaitable[T | None]],
    what: str,
) -> T | None:
    """The first answer `read` finds in any search's results; raises only when no search answered at all
    (then it is a failure to retry soon, not a «nothing found» to remember)."""
    failure: Exception | None = None
    answered = False
    for search in searches:
        for query in queries:
            try:
                results = [r for r in await search.search(query) if r.content][:MAX_EXCERPTS]
            except Exception as problem:  # noqa: BLE001  (any failure moves on to the next search)
                log.info("%s failed for %s: %s", type(search).__name__, what, type(problem).__name__)
                failure = problem
                break
            answered = True
            if results and (found := await read(results)) is not None:
                return found
    if failure and not answered:
        raise failure
    return None


async def read_json(
    client: Any, model: str, system: str, task: str, results: list[WebResult], schema: dict, name: str
) -> dict:
    """One structured-output call: the model reads the numbered excerpts and answers by the schema."""
    excerpts = "\n\n".join(
        f"[{i}] {r.title} — {r.url}\n{r.content[:EXCERPT_CHARS]}" for i, r in enumerate(results, 1)
    )
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": f"{task}\n\n<excerpts>\n{excerpts}\n</excerpts>"},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": name, "strict": True, "schema": schema},
        },
        max_completion_tokens=1500,
    )
    return json.loads(response.choices[0].message.content or "{}")
