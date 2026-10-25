"""Web search for the knowledge base. Tavily works without a key (rate-limited), so the demo needs no setup."""

import logging
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

log = logging.getLogger(__name__)

TAVILY_URL = "https://api.tavily.com/search"
# Rules 6.5 and 6.6: no OTAs. trip.com and tutu.ru also sell hotels and show up in travel searches.
EXCLUDED_DOMAINS = [
    "booking.com",
    "ostrovok.ru",
    "tutu.ru",
    "travel.yandex.ru",
    "tripadvisor.ru",
    "tripadvisor.com",
    "trip.com",
    "ru.trip.com",
    "agoda.com",
    "expedia.com",
    "hotels.com",
    "airbnb.com",
    "airbnb.ru",
    "sutochno.ru",
    "101hotels.com",
    "level.travel",
    "onetwotrip.com",
    "aviasales.ru",
    "travelata.ru",
    # social video: hard to quote and to check
    "instagram.com",
    "youtube.com",
    "tiktok.com",
    "facebook.com",
]


@dataclass(frozen=True)
class WebResult:
    url: str
    title: str
    content: str
    published: str | None = None
    score: float | None = None


class WebSearch(Protocol):
    async def search(self, query: str) -> list[WebResult]: ...


class TavilySearch:
    def __init__(self, api_key: str = "", timeout_s: float = 10.0, max_results: int = 5):
        self._headers = {"Content-Type": "application/json"}
        if api_key:
            self._headers["Authorization"] = f"Bearer {api_key}"
        else:
            self._headers["X-Tavily-Access-Mode"] = "keyless"
        self._timeout = timeout_s
        self._max_results = max_results

    async def search(self, query: str) -> list[WebResult]:
        body = {
            "query": query,
            "max_results": self._max_results,
            "search_depth": "advanced",
            "chunks_per_source": 2,
            "exclude_domains": EXCLUDED_DOMAINS,
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(TAVILY_URL, json=body, headers=self._headers)
            response.raise_for_status()
            data = response.json()
        return [
            WebResult(
                url=r["url"],
                title=r.get("title") or r["url"],
                content=r.get("content") or "",
                published=r.get("published_date"),
                score=r.get("score"),
            )
            for r in data.get("results", [])
            if r.get("url") and r.get("content")
        ]


def _strip_tracking(url: str) -> str:
    parts = urlsplit(url)
    query = urlencode([(k, v) for k, v in parse_qsl(parts.query) if not k.startswith("utm_")])
    return urlunsplit(parts._replace(query=query))


def _paragraph_around(text: str, start: int, end: int) -> str:
    left = text.rfind("\n", 0, start) + 1
    right = text.find("\n", end)
    return text[left : right if right != -1 else len(text)]


class OpenAIWebSearch:
    """OpenAI's built-in web search through the Responses API. Each cited source becomes one result, with
    the paragraphs of the answer that cite it as its content."""

    PROMPT = (
        "Найди в интернете ответ на вопрос путешественника и процитируй выдержки из источников с указанием "
        "ссылок. Не используй сайты бронирования. Вопрос: {query}"
    )

    def __init__(self, client: Any, model: str, timeout_s: float = 30.0):
        self._client = client
        self._model = model
        self._timeout = timeout_s

    async def search(self, query: str) -> list[WebResult]:
        response = await self._client.responses.create(
            model=self._model,
            tools=[{"type": "web_search"}],
            input=self.PROMPT.format(query=query),
            timeout=self._timeout,
        )
        by_url: dict[str, dict] = {}
        for item in response.output:
            if getattr(item, "type", None) != "message":
                continue
            for part in item.content:
                text = getattr(part, "text", "") or ""
                for note in getattr(part, "annotations", None) or []:
                    if getattr(note, "type", None) != "url_citation":
                        continue
                    url = _strip_tracking(note.url)
                    host = (urlsplit(url).hostname or "").removeprefix("www.")
                    if any(host == d or host.endswith(f".{d}") for d in EXCLUDED_DOMAINS):
                        continue
                    found = by_url.setdefault(
                        url, {"title": getattr(note, "title", None) or host, "parts": []}
                    )
                    paragraph = _paragraph_around(text, note.start_index, note.end_index).strip()
                    if paragraph and paragraph not in found["parts"]:
                        found["parts"].append(paragraph)
        return [WebResult(url=u, title=v["title"], content=" ".join(v["parts"])) for u, v in by_url.items()]


class FallbackSearch:
    """Tries each search in order; the next one runs only when the previous one fails (rate limit, outage)."""

    def __init__(self, searches: list[WebSearch]):
        self._searches = searches

    async def search(self, query: str) -> list[WebResult]:
        error: Exception | None = None
        for search in self._searches:
            try:
                return await search.search(query)
            except Exception as failure:  # noqa: BLE001  (any failure moves on to the next provider)
                log.warning("%s failed, trying the next search: %s", type(search).__name__, failure)
                error = failure
        raise error or RuntimeError("no web search configured")


def build_web_search(
    provider: str, api_key: str, timeout_s: float, openai_client: Any = None, openai_model: str = ""
) -> WebSearch | None:
    """tavily (default): Tavily, then OpenAI web search as a backup when the agent runs on OpenAI.
    openai: only OpenAI web search. none: no web search."""
    openai = OpenAIWebSearch(openai_client, openai_model) if openai_client and openai_model else None
    if provider == "tavily":
        tavily = TavilySearch(api_key=api_key, timeout_s=timeout_s)
        return FallbackSearch([tavily, openai]) if openai else tavily
    if provider == "openai":
        if openai is None:
            log.warning("SEARCH_PROVIDER=openai needs the agent itself to run on OpenAI, web search is off")
        return openai
    if provider not in ("", "none"):
        log.warning("Unknown SEARCH_PROVIDER %r, web search is off", provider)
    return None


def web_search_for(settings, llm) -> WebSearch | None:
    """The configured search, with OpenAI web search as a backup when the agent itself runs on OpenAI."""
    from app.llm import OpenAICompatibleLLM  # here, so this module stays free of the LLM layer otherwise

    on_openai = isinstance(llm, OpenAICompatibleLLM) and not settings.llm_base_url
    return build_web_search(
        settings.search_provider,
        settings.tavily_api_key,
        settings.search_timeout_s,
        openai_client=llm.client if on_openai else None,
        openai_model=llm.model if on_openai else "",
    )
