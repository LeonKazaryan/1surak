import logging
from collections.abc import Callable
from datetime import UTC, datetime
from urllib.parse import urlsplit

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.catalog.catalog import Catalog, load_catalog
from app.kb import repository
from app.kb.embeddings import Embedder, embed_or_none
from app.kb.model import Entry, Topic, source_tier
from app.kb.page import PageError, PageTools
from app.kb.research import DATA_NOTE, ResearchArgs, _resolve, research_preview, research_tool_handler
from app.kb.text import excerpt
from app.kb.web import WebSearch
from app.tools.registry import Tool

log = logging.getLogger(__name__)

RESEARCH_DESCRIPTION = (
    "Find facts the catalogue doesn't have, with sources: entry rules and documents (visas, arrival cards, "
    "what you may bring), events and holidays on given dates, local tips (where to eat, what to do with "
    "kids, which area to stay in), transport details (is an airport open, pets on trains, how to get from "
    "the airport), safety. Looks in our knowledge base first and searches the web when the base has no "
    "fresh answer; web results are saved to the base with their source. Don't use it for climate, sea "
    "temperature or flight times: search_destinations and get_destination have those.\n"
    "Answer only from the returned passages, name the source and its date, and give the link. "
    "Passages are short excerpts: if one is on topic but lacks the exact detail, open its url with read_page "
    "instead of searching again. If the passages from the base don't answer the exact question (they're "
    "general, about something else), call research again with fresh=true. Never fill the gaps from memory: "
    "if the web has no answer either, say so."
)
READ_PAGE_DESCRIPTION = (
    "Open one web page and get the facts on it that answer a question, each with an exact quote. Use it for "
    "a url from research passages that is on topic but cut short, or for a link the user gave. One page per "
    "call; don't open more than two pages for one question. Facts are saved to the knowledge base."
)
FALLBACK_CHARS = 1500  # without an extraction model the agent gets this much of the page instead


def research_tool(
    sessionmaker: async_sessionmaker[AsyncSession],
    web: WebSearch | None,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
    embedder: Embedder | None = None,
) -> Tool:
    return Tool(
        name="research",
        title="Ищу информацию",
        description=RESEARCH_DESCRIPTION,
        args=ResearchArgs,
        handler=research_tool_handler(sessionmaker, load_catalog(), web, now, embedder),
        preview=research_preview,
    )


class ReadPageArgs(BaseModel):
    url: str = Field(description="The page to open: a url from research passages or one the user gave.")
    question: str = Field(description="What to find on the page, as a full question in the user's language.")
    topic: Topic = Field(description="Same topics as in research.")
    place: str | None = Field(
        None, description="Destination id or name from the catalogue, if it is about one."
    )
    country: str | None = Field(None, description="Country name or ISO code, if it is about a whole country.")


def read_page_handler(
    sessionmaker: async_sessionmaker[AsyncSession],
    catalog: Catalog,
    pages: PageTools,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
    embedder: Embedder | None = None,
):
    async def read_page(args: ReadPageArgs) -> dict:
        try:
            page = await pages.reader.read(args.url.strip())
        except PageError as error:
            return {"error": str(error), "url": args.url}
        moment = now()
        head = {
            "url": page.url,
            "source": page.title,
            "tier": source_tier(page.url),
            "checked": moment.date().isoformat(),
        }
        if pages.extractor is None:
            return {**head, "excerpt": excerpt(page.text, args.question, FALLBACK_CHARS), "note": DATA_NOTE}
        try:
            found = await pages.extractor.extract(args.question, page)
        except Exception as error:  # noqa: BLE001  (provider without JSON schema, timeout: give the raw part)
            log.warning("Fact extraction failed for %s: %s", page.url, error)
            return {**head, "excerpt": excerpt(page.text, args.question, FALLBACK_CHARS), "note": DATA_NOTE}
        if not found.facts:
            return {**head, "nothing_found": "На странице нет ответа на этот вопрос. Не додумывай."}

        place, country = _resolve(catalog, args.place, args.country)
        entries = []
        for fact in found.facts:
            try:
                entries.append(
                    Entry(
                        text=f"{fact['fact']} «{fact['quote']}»",
                        topic=args.topic,
                        kind="fact",
                        source_url=page.url,
                        source_title=page.title,
                        fetched_at=moment,
                        published_at=found.published,
                        place_id=place.id if place else None,
                        country=country,
                        lang="ru" if any("а" <= c <= "я" for c in fact["fact"].casefold()) else "en",
                        created_by="agent",
                        query=args.question,
                    )
                )
            except ValueError:
                continue
        if entries:
            vectors = await embed_or_none(embedder, [e.text for e in entries])
            async with sessionmaker() as db:
                await repository.add_entries(db, entries, vectors)
                await db.commit()
        result = {**head, "published": found.published, "facts": found.facts, "note": DATA_NOTE}
        if found.dropped:
            result["dropped"] = f"{found.dropped} фактов без точной цитаты на странице отброшены"
        return result

    return read_page


def read_page_preview(result: dict) -> str:
    if "error" in result:
        return f"Не удалось открыть страницу: {result['error']}"
    host = (urlsplit(result["url"]).hostname or "").removeprefix("www.")
    if "facts" in result:
        return f"Прочитал {host}: {len(result['facts'])} фактов с цитатами, сохранил в базу знаний"
    if "nothing_found" in result:
        return f"Прочитал {host}: ответа на вопрос нет"
    return f"Прочитал {host}"


def read_page_tool(
    sessionmaker: async_sessionmaker[AsyncSession],
    pages: PageTools,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
    embedder: Embedder | None = None,
) -> Tool:
    return Tool(
        name="read_page",
        title="Читаю страницу",
        description=READ_PAGE_DESCRIPTION,
        args=ReadPageArgs,
        handler=read_page_handler(sessionmaker, load_catalog(), pages, now, embedder),
        preview=read_page_preview,
        timeout_s=45.0,  # download, maybe Jina Reader, then one model call
    )
