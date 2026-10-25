import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import anyio
from pydantic import BaseModel, ValidationError

log = logging.getLogger(__name__)

TOOL_TIMEOUT_S = 20.0
PREVIEW_MAX_CHARS = 200


@dataclass(frozen=True)
class Tool:
    """One action the agent can take.

    `title` is shown to the user while the tool runs, `description` and `args` are what the model sees.
    The handler returns plain JSON-serializable data; facts the agent quotes must come from it.
    """

    name: str
    title: str
    description: str
    args: type[BaseModel]
    handler: Callable[[Any], Awaitable[Any]]
    preview: Callable[[Any], str] | None = None

    def spec(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.args.model_json_schema(),
            },
        }


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    content: str  # what goes back to the model
    preview: str  # one line for the user
    args: dict


def _short(text: str) -> str:
    return text if len(text) <= PREVIEW_MAX_CHARS else f"{text[: PREVIEW_MAX_CHARS - 1]}…"


def _error(message: str, args: dict, preview: str) -> ToolResult:
    return ToolResult(
        ok=False, content=json.dumps({"error": message}, ensure_ascii=False), preview=preview, args=args
    )


class ToolRegistry:
    def __init__(self, tools: list[Tool] | None = None):
        self._tools: dict[str, Tool] = {}
        for tool in tools or []:
            self.add(tool)

    def add(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool {tool.name!r} is already registered")
        self._tools[tool.name] = tool

    def __bool__(self) -> bool:
        return bool(self._tools)

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def specs(self) -> list[dict]:
        return [tool.spec() for tool in self._tools.values()]

    def title(self, name: str) -> str:
        tool = self._tools.get(name)
        return tool.title if tool else name

    async def execute(self, name: str, raw_args: str) -> ToolResult:
        """Runs a tool call. Never raises: problems go back to the model as an error it can react to."""
        try:
            args = json.loads(raw_args or "{}")
        except json.JSONDecodeError:
            return _error("Arguments are not valid JSON", {}, "Не удалось разобрать параметры")
        if not isinstance(args, dict):
            return _error("Arguments must be a JSON object", {}, "Не удалось разобрать параметры")

        tool = self._tools.get(name)
        if tool is None:
            return _error(f"Unknown tool {name!r}", args, "Такого инструмента нет")

        try:
            parsed = tool.args.model_validate(args)
        except ValidationError as exc:
            details = exc.errors(include_url=False, include_context=False, include_input=False)
            return _error(f"Invalid arguments: {details}", args, "Неверные параметры")

        try:
            with anyio.fail_after(TOOL_TIMEOUT_S):
                result = await tool.handler(parsed)
        except TimeoutError:
            log.warning("Tool %s timed out", name)
            return _error("Tool timed out", args, "Не успел получить данные")
        except Exception:
            log.exception("Tool %s failed", name)
            return _error("Tool failed", args, "Не удалось получить данные")

        preview = tool.preview(result) if tool.preview else "Готово"
        return ToolResult(
            ok=True,
            content=json.dumps(result, ensure_ascii=False, default=str),
            preview=_short(preview),
            args=args,
        )
