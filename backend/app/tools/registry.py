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
    To also show something in the chat (cards, questions), it returns a ToolReply instead.
    """

    name: str
    title: str
    description: str
    args: type[BaseModel]
    handler: Callable[[Any], Awaitable[Any]]
    preview: Callable[[Any], str] | None = None
    # A few numbers about the work, for the progress the user watches: «120 направлений → 14 подходят».
    facts: Callable[[Any], list[dict]] | None = None
    # A tool the model must call after this one before it answers, e.g. show the places it found as cards.
    then: str | None = None

    # Runs longer than TOOL_TIMEOUT_S, e.g. reading a web page and pulling facts out of it.
    timeout_s: float | None = None

    def spec(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": compact_schema(self.args.model_json_schema()),
            },
        }


def compact_schema(node: Any) -> Any:
    """Pydantic's JSON schema with the parts the model doesn't need: a `title` on every field and
    `anyOf [X, null]` with `default: null` on every optional one. The specs go with every model call,
    so this halves a fixed cost. Optional fields stay optional: they are not in `required`."""
    if isinstance(node, list):
        return [compact_schema(item) for item in node]
    if not isinstance(node, dict):
        return node
    out = {k: compact_schema(v) for k, v in node.items() if k != "title" or not isinstance(v, str)}
    if "properties" in node:  # `title` here is a field name, not a label
        out["properties"] = {k: compact_schema(v) for k, v in node["properties"].items()}
    variants = out.get("anyOf")
    if isinstance(variants, list) and len(variants) == 2 and {"type": "null"} in variants:
        out.pop("anyOf")
        out = {**next(v for v in variants if v != {"type": "null"}), **out}
    if "default" in out and out["default"] is None:
        out.pop("default")
    return out


def _drop_empty(value: Any) -> Any:
    """None means 'unknown' everywhere in tool results, so a missing key says the same in fewer tokens."""
    if isinstance(value, dict):
        return {k: _drop_empty(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_drop_empty(v) for v in value]
    return value


@dataclass(frozen=True)
class ToolReply:
    """A result for the model plus what the user sees: `text` as the agent's words, `event` as a chat widget.
    `ends_turn` hands the turn back to the user, e.g. after asking a question."""

    result: Any
    event: dict
    text: str = ""
    ends_turn: bool = False


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    content: str  # what goes back to the model
    preview: str  # one line for the user
    args: dict
    event: dict | None = None
    text: str = ""
    ends_turn: bool = False
    facts: tuple[dict, ...] = ()


def fact(value: int, forms: tuple[str, str, str], rest: str = "") -> dict:
    """{value, label}: «120 направлений из Москвы», the label agreeing with the number."""
    tail = abs(value) % 100
    word = (
        forms[2]
        if 11 <= tail <= 14
        else forms[0]
        if tail % 10 == 1
        else forms[1]
        if 2 <= tail % 10 <= 4
        else forms[2]
    )
    return {"value": value, "label": f"{word} {rest}".strip()}


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

    def extended(self, tools: list[Tool]) -> "ToolRegistry":
        """A new registry with these tools added, e.g. the ones bound to a single chat."""
        return ToolRegistry([*self._tools.values(), *tools])

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
            with anyio.fail_after(tool.timeout_s or TOOL_TIMEOUT_S):
                result = await tool.handler(parsed)
        except TimeoutError:
            log.warning("Tool %s timed out", name)
            return _error("Tool timed out", args, "Не успел получить данные")
        except Exception:
            log.exception("Tool %s failed", name)
            return _error("Tool failed", args, "Не удалось получить данные")

        reply = result if isinstance(result, ToolReply) else None
        if reply:
            result = reply.result
        preview = tool.preview(result) if tool.preview else "Готово"
        try:
            facts = tuple(tool.facts(result)) if tool.facts else ()
        except (KeyError, TypeError, ValueError):  # a fact is a nicety, never a failure
            facts = ()
        return ToolResult(
            ok=True,
            content=json.dumps(_drop_empty(result), ensure_ascii=False, default=str, separators=(",", ":")),
            preview=_short(preview),
            args=args,
            event=reply.event if reply else None,
            text=reply.text if reply else "",
            ends_turn=bool(reply and reply.ends_turn),
            facts=facts,
        )
