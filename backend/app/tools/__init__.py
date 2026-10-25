from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.tools.registry import Tool, ToolRegistry, ToolReply, ToolResult

__all__ = ["Tool", "ToolRegistry", "ToolReply", "ToolResult", "build_registry"]


def build_registry(sessionmaker: async_sessionmaker[AsyncSession], web=None) -> ToolRegistry:
    """The tools the agent can call. Flights, hotels and the rest get added here.
    `web` is the web search for the knowledge base; None keeps research to the stored base."""
    # imported here: these modules import Tool from this package
    from app.catalog.tools import catalog_tools
    from app.kb.tools import research_tool

    return ToolRegistry([*catalog_tools(sessionmaker), research_tool(sessionmaker, web)])
