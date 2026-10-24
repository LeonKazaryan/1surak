import asyncio
from types import SimpleNamespace

from app.config import Settings
from app.llm import OpenAICompatibleLLM, StubLLM, build_llm


async def collect(stream) -> list[str]:
    return [chunk async for chunk in stream]


def chunk(content):
    return SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=content))])


class FakeCompletions:
    def __init__(self, chunks):
        self.chunks = chunks
        self.kwargs = None

    async def create(self, **kwargs):
        self.kwargs = kwargs

        async def iterate():
            for c in self.chunks:
                yield c

        return iterate()


def test_should_build_stub_when_api_key_is_missing():
    assert isinstance(build_llm(Settings(llm_api_key="")), StubLLM)


def test_should_build_openai_compatible_client_when_api_key_is_set():
    llm = build_llm(Settings(llm_api_key="key", llm_base_url="http://llm.local/v1", llm_model="m"))

    assert isinstance(llm, OpenAICompatibleLLM)


def test_should_explain_missing_key_in_stub_reply():
    text = "".join(asyncio.run(collect(StubLLM().stream([]))))

    assert "LLM_API_KEY" in text


def test_should_stream_delta_text_and_skip_empty_chunks():
    completions = FakeCompletions([chunk("Привет"), chunk(None), SimpleNamespace(choices=[]), chunk("!")])
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    llm = OpenAICompatibleLLM(client=client, model="test-model")

    messages = [{"role": "user", "content": "hi"}]
    out = asyncio.run(collect(llm.stream(messages)))

    assert out == ["Привет", "!"]
    assert completions.kwargs["model"] == "test-model"
    assert completions.kwargs["stream"] is True
    assert completions.kwargs["messages"] == messages
