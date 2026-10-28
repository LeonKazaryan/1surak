import asyncio
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Protocol

from openai import AsyncOpenAI

from app.config import Settings

STUB_REPLY = (
    "LLM пока не подключён: задайте LLM_API_KEY и LLM_MODEL в .env и перезапустите сервис. "
    "Интерфейс, история чатов и стриминг уже работают, логику агента подключим следующим шагом."
)
STUB_TOKEN_DELAY_S = 0.03


@dataclass(frozen=True)
class TextDelta:
    text: str


@dataclass(frozen=True)
class ToolStarting:
    """The model has begun a call to this tool and is still writing its arguments: a long intro takes seconds,
    and the screen can say what is coming meanwhile."""

    name: str


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: str  # raw JSON string, exactly as the model produced it


@dataclass(frozen=True)
class Usage:
    """Tokens one model call used. `cached` is the part of `input` served from the provider's prompt cache."""

    input: int
    output: int
    cached: int = 0


LLMEvent = TextDelta | ToolStarting | ToolCall | Usage

# OpenAI routes requests with the same key to the same cache, so the shared prefix (tools and system prompt)
# is cached across chats, not only within one.
PROMPT_CACHE_KEY = "1surak-agent"


class LLM(Protocol):
    def stream(
        self, messages: list[dict], tools: list[dict] | None = None, tool_choice: str | None = None
    ) -> AsyncIterator[LLMEvent]:
        """`tool_choice` names a tool the model must call this time."""
        ...


class StubLLM:
    async def stream(
        self, messages: list[dict], tools: list[dict] | None = None, tool_choice: str | None = None
    ) -> AsyncIterator[LLMEvent]:
        for token in re.findall(r"\S+\s*", STUB_REPLY):
            await asyncio.sleep(STUB_TOKEN_DELAY_S)
            yield TextDelta(token)


class OpenAICompatibleLLM:
    def __init__(self, client: Any, model: str, openai: bool = False, reasoning_effort: str = ""):
        self._client = client
        self._model = model
        self._openai = openai  # the real OpenAI API, not another provider behind the same SDK
        self._reasoning_effort = reasoning_effort

    @property
    def client(self) -> Any:
        return self._client

    @property
    def model(self) -> str:
        return self._model

    def stream(
        self, messages: list[dict], tools: list[dict] | None = None, tool_choice: str | None = None
    ) -> AsyncIterator[LLMEvent]:
        # OpenAI's newer models call tools on Chat Completions only with reasoning off
        if self._openai:
            return self._stream_responses(messages, tools, tool_choice)
        return self._stream_chat(messages, tools, tool_choice)

    async def _stream_responses(
        self, messages: list[dict], tools: list[dict] | None, tool_choice: str | None
    ) -> AsyncIterator[LLMEvent]:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "input": _responses_input(messages),
            "stream": True,
            "store": False,
            "prompt_cache_key": PROMPT_CACHE_KEY,
        }
        if self._reasoning_effort:
            kwargs["reasoning"] = {"effort": self._reasoning_effort}
        if tools:
            kwargs["tools"] = [_responses_tool(spec["function"]) for spec in tools]
            if tool_choice:
                kwargs["tool_choice"] = {"type": "function", "name": tool_choice}
        # shortcut: reasoning items are not sent back between tool rounds, so each round thinks afresh;
        # pass them with include=["reasoning.encrypted_content"] if quality or cost asks for it
        response = await self._client.responses.create(**kwargs)

        calls: list[ToolCall] = []
        usage: Usage | None = None
        async for event in response:
            if event.type == "response.output_text.delta":
                yield TextDelta(event.delta)
            elif event.type == "response.output_item.added" and event.item.type == "function_call":
                yield ToolStarting(event.item.name)
            elif event.type == "response.output_item.done" and event.item.type == "function_call":
                calls.append(
                    ToolCall(id=event.item.call_id, name=event.item.name, arguments=event.item.arguments)
                )
            elif event.type in ("response.completed", "response.incomplete") and event.response.usage:
                raw = event.response.usage
                cached = getattr(raw.input_tokens_details, "cached_tokens", 0) or 0
                usage = Usage(input=raw.input_tokens, output=raw.output_tokens, cached=cached)
            elif event.type == "response.failed":
                raise RuntimeError(f"OpenAI response failed: {event.response.error}")
            elif event.type == "error":
                raise RuntimeError(f"OpenAI stream error: {event.code}: {event.message}")

        for call in calls:
            yield call
        if usage:
            yield usage

    async def _stream_chat(
        self, messages: list[dict], tools: list[dict] | None, tool_choice: str | None
    ) -> AsyncIterator[LLMEvent]:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if tools:  # some providers reject an empty tools list
            kwargs["tools"] = tools
            if tool_choice:
                kwargs["tool_choice"] = {"type": "function", "function": {"name": tool_choice}}
        response = await self._client.chat.completions.create(**kwargs)

        # Tool calls arrive in fragments keyed by index; they are only usable once complete.
        calls: dict[int, dict[str, str]] = {}
        usage: Usage | None = None
        async for chunk in response:
            if getattr(chunk, "usage", None):
                usage = _usage(chunk.usage)
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta.content:
                yield TextDelta(delta.content)
            for fragment in getattr(delta, "tool_calls", None) or []:
                call = calls.setdefault(fragment.index, {"id": "", "name": "", "arguments": ""})
                if fragment.id:
                    call["id"] = fragment.id
                function = fragment.function
                if function is not None:
                    named = bool(call["name"])
                    call["name"] += function.name or ""
                    call["arguments"] += function.arguments or ""
                    if call["name"] and not named:  # the name comes first, the arguments take a while
                        yield ToolStarting(call["name"])

        for index in sorted(calls):
            call = calls[index]
            yield ToolCall(id=call["id"] or f"call_{index}", name=call["name"], arguments=call["arguments"])
        if usage:
            yield usage


def _responses_input(messages: list[dict]) -> list[dict]:
    """Chat Completions turns as Responses API input items: tool calls and their results become their own items."""
    items: list[dict] = []
    for message in messages:
        if message["role"] == "tool":
            items.append(
                {
                    "type": "function_call_output",
                    "call_id": message["tool_call_id"],
                    "output": message["content"],
                }
            )
            continue
        if message.get("content"):
            items.append({"role": message["role"], "content": message["content"]})
        for call in message.get("tool_calls") or []:
            function = call["function"]
            items.append(
                {
                    "type": "function_call",
                    "call_id": call["id"],
                    "name": function["name"],
                    "arguments": function["arguments"],
                }
            )
    return items


def _responses_tool(function: dict) -> dict:
    # not strict: our schemas have optional fields, which strict mode rejects
    return {
        "type": "function",
        "name": function["name"],
        "description": function.get("description"),
        "parameters": function.get("parameters"),
        "strict": False,
    }


def _usage(raw: Any) -> Usage:
    details = getattr(raw, "prompt_tokens_details", None)
    return Usage(
        input=raw.prompt_tokens or 0,
        output=raw.completion_tokens or 0,
        cached=getattr(details, "cached_tokens", None) or 0,
    )


def build_llm(settings: Settings) -> LLM:
    if not (settings.llm_api_key and settings.llm_model):
        return StubLLM()
    client = AsyncOpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url or None,
        timeout=settings.llm_timeout_s,
    )
    return OpenAICompatibleLLM(
        client=client,
        model=settings.llm_model,
        openai=not settings.llm_base_url,
        reasoning_effort=settings.llm_reasoning_effort,
    )
