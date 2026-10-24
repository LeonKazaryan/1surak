import asyncio
import re
from collections.abc import AsyncIterator
from typing import Any, Protocol

from openai import AsyncOpenAI

from app.config import Settings

STUB_REPLY = (
    "LLM пока не подключён: задайте LLM_API_KEY и LLM_MODEL в .env и перезапустите сервис. "
    "Интерфейс, история чатов и стриминг уже работают, логику агента подключим следующим шагом."
)
STUB_TOKEN_DELAY_S = 0.03


class LLM(Protocol):
    def stream(self, messages: list[dict]) -> AsyncIterator[str]: ...


class StubLLM:
    async def stream(self, messages: list[dict]) -> AsyncIterator[str]:
        for token in re.findall(r"\S+\s*", STUB_REPLY):
            await asyncio.sleep(STUB_TOKEN_DELAY_S)
            yield token


class OpenAICompatibleLLM:
    def __init__(self, client: Any, model: str):
        self._client = client
        self._model = model

    async def stream(self, messages: list[dict]) -> AsyncIterator[str]:
        response = await self._client.chat.completions.create(
            model=self._model, messages=messages, stream=True
        )
        async for chunk in response:
            if not chunk.choices:
                continue
            text = chunk.choices[0].delta.content
            if text:
                yield text


def build_llm(settings: Settings) -> LLM:
    if not (settings.llm_api_key and settings.llm_model):
        return StubLLM()
    client = AsyncOpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url or None,
        timeout=settings.llm_timeout_s,
    )
    return OpenAICompatibleLLM(client=client, model=settings.llm_model)
