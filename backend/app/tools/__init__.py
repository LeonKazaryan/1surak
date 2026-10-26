from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.tools.registry import Tool, ToolRegistry, ToolReply, ToolResult

__all__ = ["Tool", "ToolRegistry", "ToolReply", "ToolResult", "build_registry"]


def build_registry(
    sessionmaker: async_sessionmaker[AsyncSession],
    web=None,
    pages=None,
    flights=None,
    embedder=None,
    climate=None,
    directions=None,
) -> ToolRegistry:
    """The tools the agent can call. Hotels and the rest get added here.
    `web` is the web search for the knowledge base; None keeps research to the stored base.
    `pages` (app.kb.page.PageTools) adds read_page; None leaves it out.
    `flights` gives real tickets; None means no flight data, and the agent says so.
    `embedder` adds search by meaning; None searches by words only."""
    # imported here: these modules import Tool from this package
    from app.catalog.tools import catalog_tools
    from app.flights import NoFlights
    from app.flights.tools import flight_tools
    from app.kb.tools import read_page_tool, research_tool

    flights = flights or NoFlights()
    tools = [
        *catalog_tools(sessionmaker, flights=flights, climate=climate, directions=directions),
        *flight_tools(flights),
        research_tool(sessionmaker, web, embedder=embedder),
    ]
    if pages is not None:
        tools.append(read_page_tool(sessionmaker, pages, embedder=embedder))
    return ToolRegistry(tools)
