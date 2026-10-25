from app.tools.registry import Tool, ToolRegistry, ToolResult

__all__ = ["Tool", "ToolRegistry", "ToolResult", "build_registry"]


def build_registry() -> ToolRegistry:
    """The tools the agent can call. Trip tools (destinations, flights, hotels…) get added here."""
    return ToolRegistry()
