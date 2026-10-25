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


LLMEvent = TextDelta | ToolCall


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
    def __init__(self, client: Any, model: str):
        self._client = client
        self._model = model

    @property
    def client(self) -> Any:
        return self._client

    @property
    def model(self) -> str:
        return self._model

    async def stream(
        self, messages: list[dict], tools: list[dict] | None = None, tool_choice: str | None = None
    ) -> AsyncIterator[LLMEvent]:
        kwargs: dict[str, Any] = {"model": self._model, "messages": messages, "stream": True}
        if tools:  # some providers reject an empty tools list
            kwargs["tools"] = tools
            if tool_choice:
                kwargs["tool_choice"] = {"type": "function", "function": {"name": tool_choice}}
        response = await self._client.chat.completions.create(**kwargs)

        # Tool calls arrive in fragments keyed by index; they are only usable once complete.
        calls: dict[int, dict[str, str]] = {}
        async for chunk in response:
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


def build_llm(settings: Settings) -> LLM:
    if not (settings.llm_api_key and settings.llm_model):
        return StubLLM()
    client = AsyncOpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url or None,
        timeout=settings.llm_timeout_s,
    )
    return OpenAICompatibleLLM(client=client, model=settings.llm_model)
