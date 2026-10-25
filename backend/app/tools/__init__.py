from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.tools.registry import Tool, ToolRegistry, ToolResult

__all__ = ["Tool", "ToolRegistry", "ToolResult", "build_registry"]


def build_registry(sessionmaker: async_sessionmaker[AsyncSession]) -> ToolRegistry:
    """The tools the agent can call. Flights, hotels and the rest get added here."""
    from app.catalog.tools import catalog_tools  # the catalogue imports Tool from this package

    return ToolRegistry(catalog_tools(sessionmaker))
