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


LLMEvent = TextDelta | ToolCall | Usage

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
    def __init__(self, client: Any, model: str, openai: bool = False):
        self._client = client
        self._model = model
        self._openai = openai  # the real OpenAI API, not another provider behind the same SDK

    @property
    def client(self) -> Any:
        return self._client

    @property
    def model(self) -> str:
        return self._model

    async def stream(
        self, messages: list[dict], tools: list[dict] | None = None, tool_choice: str | None = None
    ) -> AsyncIterator[LLMEvent]:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if self._openai:
            kwargs["prompt_cache_key"] = PROMPT_CACHE_KEY
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
                    call["name"] += function.name or ""
                    call["arguments"] += function.arguments or ""

        for index in sorted(calls):
            call = calls[index]
            yield ToolCall(id=call["id"] or f"call_{index}", name=call["name"], arguments=call["arguments"])
        if usage:
            yield usage


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
    return OpenAICompatibleLLM(client=client, model=settings.llm_model, openai=not settings.llm_base_url)
