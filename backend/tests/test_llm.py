import asyncio
from types import SimpleNamespace

from app.config import Settings
from app.llm import OpenAICompatibleLLM, StubLLM, TextDelta, ToolCall, build_llm


async def collect(stream) -> list[str]:
    return [chunk async for chunk in stream]


def chunk(content=None, tool_calls=None):
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content=content, tool_calls=tool_calls))]
    )


def fragment(index, id=None, name=None, arguments=None):
    return SimpleNamespace(index=index, id=id, function=SimpleNamespace(name=name, arguments=arguments))


def llm_with(chunks):
    completions = FakeCompletions(chunks)
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    return OpenAICompatibleLLM(client=client, model="test-model"), completions


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
    text = "".join(e.text for e in asyncio.run(collect(StubLLM().stream([]))))

    assert "LLM_API_KEY" in text


def test_should_stream_delta_text_and_skip_empty_chunks():
    llm, completions = llm_with([chunk("Привет"), chunk(None), SimpleNamespace(choices=[]), chunk("!")])

    messages = [{"role": "user", "content": "hi"}]
    out = asyncio.run(collect(llm.stream(messages)))

    assert out == [TextDelta("Привет"), TextDelta("!")]
    assert completions.kwargs["model"] == "test-model"
    assert completions.kwargs["stream"] is True
    assert completions.kwargs["messages"] == messages
    assert "tools" not in completions.kwargs


def test_should_assemble_tool_calls_from_streamed_fragments():
    llm, completions = llm_with(
        [
            chunk("Сейчас посмотрю."),
            chunk(tool_calls=[fragment(0, id="call_a", name="get_weather", arguments='{"ci')]),
            chunk(tool_calls=[fragment(0, arguments='ty": "Сочи"}')]),
            chunk(tool_calls=[fragment(1, id="call_b", name="get_flights", arguments="{}")]),
        ]
    )
    tools = [{"type": "function", "function": {"name": "get_weather"}}]

    out = asyncio.run(collect(llm.stream([], tools)))

    assert out == [
        TextDelta("Сейчас посмотрю."),
        ToolCall(id="call_a", name="get_weather", arguments='{"city": "Сочи"}'),
        ToolCall(id="call_b", name="get_flights", arguments="{}"),
    ]
    assert completions.kwargs["tools"] == tools
