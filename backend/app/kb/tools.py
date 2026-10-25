from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.catalog.catalog import load_catalog
from app.kb.research import ResearchArgs, research_preview, research_tool_handler
from app.kb.web import WebSearch
from app.tools.registry import Tool

RESEARCH_DESCRIPTION = (
    "Find facts the catalogue doesn't have, with sources: entry rules and documents (visas, arrival cards, "
    "what you may bring), events and holidays on given dates, local tips (where to eat, what to do with "
    "kids, which area to stay in), transport details (is an airport open, pets on trains, how to get from "
    "the airport), safety. Looks in our knowledge base first and searches the web when the base has no "
    "fresh answer; web results are saved to the base with their source. Don't use it for climate, sea "
    "temperature or flight times: search_destinations and get_destination have those.\n"
    "Answer only from the returned passages, name the source and its date, and give the link. "
    "If the passages from the base don't answer the exact question (they're general, about something "
    "else), call research again with fresh=true. Never fill the gaps from memory: if the web has no "
    "answer either, say so."
)


def research_tool(
    sessionmaker: async_sessionmaker[AsyncSession],
    web: WebSearch | None,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> Tool:
    return Tool(
        name="research",
        title="Ищу информацию",
        description=RESEARCH_DESCRIPTION,
        args=ResearchArgs,
        handler=research_tool_handler(sessionmaker, load_catalog(), web, now),
        preview=research_preview,
    )
