from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.tools.registry import Tool, ToolRegistry, ToolReply, ToolResult

__all__ = ["Tool", "ToolRegistry", "ToolReply", "ToolResult", "build_registry"]


def build_registry(sessionmaker: async_sessionmaker[AsyncSession], web=None, pages=None) -> ToolRegistry:
    """The tools the agent can call. Flights, hotels and the rest get added here.
    `web` is the web search for the knowledge base; None keeps research to the stored base.
    `pages` (app.kb.page.PageTools) adds read_page; None leaves it out."""
    # imported here: these modules import Tool from this package
    from app.catalog.tools import catalog_tools
    from app.kb.tools import read_page_tool, research_tool

    tools = [*catalog_tools(sessionmaker), research_tool(sessionmaker, web)]
    if pages is not None:
        tools.append(read_page_tool(sessionmaker, pages))
    return ToolRegistry(tools)
