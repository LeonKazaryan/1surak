import asyncio
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.llm import OpenAICompatibleLLM, StubLLM, TextDelta, ToolCall, Usage, build_llm


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


def test_should_force_the_named_tool_only_when_tools_are_sent():
    llm, completions = llm_with([chunk(tool_calls=[fragment(0, id="c", name="show", arguments="{}")])])
    tools = [{"type": "function", "function": {"name": "show"}}]

    asyncio.run(collect(llm.stream([], tools, "show")))

    assert completions.kwargs["tool_choice"] == {"type": "function", "function": {"name": "show"}}
    llm, completions = llm_with([chunk("Привет")])
    asyncio.run(collect(llm.stream([], None, "show")))
    assert "tool_choice" not in completions.kwargs


def test_should_accept_openai_api_key_as_the_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "from-openai-var")
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    assert Settings(_env_file=None).llm_api_key == "from-openai-var"


def test_should_prefer_llm_api_key_over_openai_api_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "openai")
    monkeypatch.setenv("LLM_API_KEY", "llm")

    assert Settings(_env_file=None).llm_api_key == "llm"


def test_should_report_token_usage_from_chat_completions():
    usage = SimpleNamespace(
        prompt_tokens=1500, completion_tokens=40, prompt_tokens_details=SimpleNamespace(cached_tokens=1024)
    )
    llm, completions = llm_with([chunk("Hi"), SimpleNamespace(choices=[], usage=usage)])

    out = asyncio.run(collect(llm.stream([])))

    assert out == [TextDelta("Hi"), Usage(input=1500, output=40, cached=1024)]
    assert completions.kwargs["stream_options"] == {"include_usage": True}
    assert "prompt_cache_key" not in completions.kwargs


def event(type, **fields):
    return SimpleNamespace(type=type, **fields)


def openai_with(events, reasoning_effort=""):
    responses = FakeCompletions(events)
    client = SimpleNamespace(responses=responses)
    return OpenAICompatibleLLM(
        client, "gpt-6-luna", openai=True, reasoning_effort=reasoning_effort
    ), responses


DONE = event(
    "response.completed",
    response=SimpleNamespace(
        usage=SimpleNamespace(
            input_tokens=1500, output_tokens=40, input_tokens_details=SimpleNamespace(cached_tokens=1024)
        )
    ),
)


def test_should_send_openai_turns_and_tools_through_the_responses_api():
    llm, responses = openai_with([DONE], reasoning_effort="low")
    messages = [
        {"role": "system", "content": "Ты турагент"},
        {"role": "user", "content": "Море в ноябре"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {"id": "call_a", "type": "function", "function": {"name": "search", "arguments": '{"m": 11}'}}
            ],
        },
        {"role": "tool", "tool_call_id": "call_a", "content": "Анталья"},
    ]
    tools = [{"type": "function", "function": {"name": "show", "description": "Показать", "parameters": {}}}]

    asyncio.run(collect(llm.stream(messages, tools, "show")))

    kwargs = responses.kwargs
    assert kwargs["input"] == [
        {"role": "system", "content": "Ты турагент"},
        {"role": "user", "content": "Море в ноябре"},
        {"type": "function_call", "call_id": "call_a", "name": "search", "arguments": '{"m": 11}'},
        {"type": "function_call_output", "call_id": "call_a", "output": "Анталья"},
    ]
    assert kwargs["tools"] == [
        {"type": "function", "name": "show", "description": "Показать", "parameters": {}, "strict": False}
    ]
    assert kwargs["tool_choice"] == {"type": "function", "name": "show"}
    assert kwargs["reasoning"] == {"effort": "low"}
    assert kwargs["store"] is False
    assert kwargs["stream"] is True
    assert kwargs["prompt_cache_key"]


def test_should_stream_text_then_tool_calls_and_usage_from_openai_events():
    call = SimpleNamespace(type="function_call", call_id="call_a", name="show", arguments="{}")
    llm, _ = openai_with(
        [
            event("response.output_text.delta", delta="Сейчас "),
            event("response.output_item.done", item=SimpleNamespace(type="reasoning")),
            event("response.output_item.done", item=call),
            event("response.output_text.delta", delta="покажу."),
            DONE,
        ]
    )

    out = asyncio.run(collect(llm.stream([])))

    assert out == [
        TextDelta("Сейчас "),
        TextDelta("покажу."),
        ToolCall(id="call_a", name="show", arguments="{}"),
        Usage(input=1500, output=40, cached=1024),
    ]


def test_should_leave_the_effort_to_the_model_when_it_is_not_set():
    llm, responses = openai_with([DONE])

    asyncio.run(collect(llm.stream([{"role": "user", "content": "hi"}])))

    assert "reasoning" not in responses.kwargs
    assert "tools" not in responses.kwargs


def test_should_fail_the_turn_when_openai_reports_a_failed_response():
    error = SimpleNamespace(code="server_error", message="boom")
    llm, _ = openai_with([event("response.failed", response=SimpleNamespace(error=error))])

    with pytest.raises(RuntimeError, match="boom"):
        asyncio.run(collect(llm.stream([])))


def test_should_pass_the_configured_effort_to_openai(monkeypatch):
    responses = FakeCompletions([DONE])
    monkeypatch.setattr("app.llm.AsyncOpenAI", lambda **_: SimpleNamespace(responses=responses))

    settings = Settings(
        llm_api_key="k", llm_base_url="", llm_model="gpt-6-luna", llm_reasoning_effort="medium"
    )
    llm = build_llm(settings)
    asyncio.run(collect(llm.stream([])))

    assert responses.kwargs["reasoning"] == {"effort": "medium"}


def test_should_reject_an_unknown_effort():
    with pytest.raises(ValidationError):
        Settings(llm_reasoning_effort="turbo")
