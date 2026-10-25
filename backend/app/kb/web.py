"""Web search for the knowledge base. Brave (with a key) is tried first, then Tavily, which works without a key
(rate-limited), so the demo needs no setup, then OpenAI's own web search when the agent runs on OpenAI."""

import logging
import re
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

log = logging.getLogger(__name__)

TAVILY_URL = "https://api.tavily.com/search"
BRAVE_URL = "https://api.search.brave.com/res/v1/llm/context"
CYRILLIC = re.compile(r"[а-яё]", re.IGNORECASE)
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


def excluded(url: str) -> bool:
    host = (urlsplit(url).hostname or "").casefold().removeprefix("www.")
    return any(host == d or host.endswith(f".{d}") for d in EXCLUDED_DOMAINS)


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


class BraveSearch:
    """Brave's LLM Context endpoint: its own index, and the text of each page already cut to the parts about
    the query, so there is no separate scraping step. The token budget is kept small on purpose: a stored
    passage is capped at 1500 characters anyway, and everything here goes into the model's context."""

    # Inline Goggle: Brave drops these sites before ranking, so they don't take the few result slots.
    GOGGLE = "\n".join(f"$discard,site={d}" for d in EXCLUDED_DOMAINS)

    def __init__(self, api_key: str, timeout_s: float = 10.0, max_results: int = 5, transport=None):
        self._headers = {"Accept": "application/json", "X-Subscription-Token": api_key}
        self._timeout = timeout_s
        self._max_results = max_results
        self._transport = transport  # tests pass an httpx.MockTransport

    async def search(self, query: str) -> list[WebResult]:
        params = {
            "q": query[:400],
            "country": "ALL",
            "search_lang": "ru" if CYRILLIC.search(query) else "en",
            "count": 10,
            "maximum_number_of_urls": self._max_results,
            "maximum_number_of_tokens": 2048,
            "maximum_number_of_tokens_per_url": 512,
            "maximum_number_of_snippets_per_url": 3,
            "context_threshold_mode": "balanced",
            "goggles": self.GOGGLE,
        }
        async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
            response = await client.get(BRAVE_URL, params=params, headers=self._headers)
            response.raise_for_status()
            data = response.json()
        sources = data.get("sources") or {}
        results = []
        for item in (data.get("grounding") or {}).get("generic") or []:
            url, snippets = item.get("url"), [s for s in item.get("snippets") or [] if isinstance(s, str)]
            if not url or not snippets or excluded(url):
                continue
            age = (sources.get(url) or {}).get("age") or []  # [full date, YYYY-MM-DD, relative, ISO]
            results.append(
                WebResult(
                    url=url,
                    title=item.get("title") or url,
                    content=" ".join(snippets),
                    published=age[1] if len(age) > 1 else None,
                )
            )
        return results


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
                    if excluded(url):
                        continue
                    found = by_url.setdefault(
                        url, {"title": getattr(note, "title", None) or host, "parts": []}
                    )
                    paragraph = _paragraph_around(text, note.start_index, note.end_index).strip()
                    if paragraph and paragraph not in found["parts"]:
                        found["parts"].append(paragraph)
        return [WebResult(url=u, title=v["title"], content=" ".join(v["parts"])) for u, v in by_url.items()]


class FallbackSearch:
    """Tries each search in order; the next one runs when the previous one fails (rate limit, outage)
    or finds nothing. Raises only when every search failed."""

    def __init__(self, searches: list[WebSearch]):
        self._searches = searches

    async def search(self, query: str) -> list[WebResult]:
        error: Exception | None = None
        answered = False
        for search in self._searches:
            try:
                results = await search.search(query)
            except Exception as failure:  # noqa: BLE001  (any failure moves on to the next provider)
                log.warning("%s failed, trying the next search: %s", type(search).__name__, failure)
                error = failure
                continue
            if results:
                return results
            answered = True
            log.info("%s found nothing for %r, trying the next search", type(search).__name__, query)
        if answered:
            return []
        raise error or RuntimeError("no web search configured")


def build_web_search(
    provider: str,
    api_key: str,
    timeout_s: float,
    openai_client: Any = None,
    openai_model: str = "",
    brave_key: str = "",
) -> WebSearch | None:
    """auto (default): Brave when there is a key, then Tavily, then OpenAI web search when the agent runs on
    OpenAI. brave / tavily: that one first, the rest as backups. openai: only OpenAI web search. none: off."""
    openai = OpenAIWebSearch(openai_client, openai_model) if openai_client and openai_model else None
    if provider in ("auto", "brave", "tavily"):
        brave = BraveSearch(brave_key, timeout_s=timeout_s) if brave_key else None
        if provider == "brave" and brave is None:
            log.warning("SEARCH_PROVIDER=brave needs BRAVE_API_KEY, using Tavily")
        tavily = TavilySearch(api_key=api_key, timeout_s=timeout_s)
        order = [tavily, brave] if provider == "tavily" else [brave, tavily]
        chain = [s for s in [*order, openai] if s is not None]
        return chain[0] if len(chain) == 1 else FallbackSearch(chain)
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
        brave_key=settings.brave_api_key,
    )
