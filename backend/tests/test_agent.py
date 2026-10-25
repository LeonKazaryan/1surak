import asyncio
import json
from datetime import datetime

from pydantic import BaseModel

from app import agent
from app.llm import ToolCall
from app.tools import Tool, ToolRegistry
from tests.conftest import FakeLLM

FIXED_NOW = datetime(2026, 10, 24, 12, 0, tzinfo=agent.MSK)


class CityArgs(BaseModel):
    city: str


async def _weather(args: CityArgs) -> dict:
    return {"city": args.city, "sea_c": 26}


async def _broken(args: CityArgs) -> dict:
    raise RuntimeError("db password is hunter2")


def registry() -> ToolRegistry:
    return ToolRegistry(
        [
            Tool(
                name="get_weather",
                title="Смотрю погоду",
                description="Sea temperature for a city",
                args=CityArgs,
                handler=_weather,
                preview=lambda r: f"{r['city']}: море {r['sea_c']} °C",
            ),
            Tool(name="broken", title="Ломаюсь", description="Always fails", args=CityArgs, handler=_broken),
        ]
    )


def run(llm: FakeLLM, tools: ToolRegistry | None = None, query: str = "Хочу к морю") -> list[dict]:
    async def collect():
        turns = [{"role": "user", "content": query}]
        return [e async for e in agent.run(llm, turns, tools, now=lambda: FIXED_NOW)]

    return asyncio.run(collect())


def text_of(events: list[dict]) -> str:
    return "".join(e["text"] for e in events if e["type"] == "assistant_token")


def call(name: str, args: str, call_id: str = "c1") -> ToolCall:
    return ToolCall(id=call_id, name=name, arguments=args)


def test_should_answer_directly_and_not_send_tools_when_none_are_registered():
    llm = FakeLLM(chunks=["При", "вет"])

    events = run(llm)

    assert [e["type"] for e in events] == ["assistant_token", "assistant_token"]
    assert llm.tools_seen == [None]


def test_should_put_todays_date_in_the_system_prompt():
    llm = FakeLLM()

    run(llm)

    system = llm.conversations[0][0]
    assert system["role"] == "system"
    assert "2026-10-24" in system["content"] and "суббота" in system["content"]


def test_should_run_requested_tool_and_feed_result_back_before_answering():
    llm = FakeLLM(rounds=[[call("get_weather", '{"city": "Анталья"}')], ["Море 26 °C."]])

    events = run(llm, registry())

    assert [e["type"] for e in events] == ["tool_start", "tool_end", "assistant_token"]
    assert events[0] == {
        "type": "tool_start",
        "name": "get_weather",
        "title": "Смотрю погоду",
        "args": {"city": "Анталья"},
    }
    assert events[1]["ok"] is True
    assert events[1]["output_preview"] == "Анталья: море 26 °C"

    assert [t["function"]["name"] for t in llm.tools_seen[0]] == ["get_weather", "broken"]
    second_call = llm.conversations[1]
    assistant, tool_msg = second_call[-2], second_call[-1]
    assert assistant["tool_calls"][0]["function"] == {
        "name": "get_weather",
        "arguments": '{"city": "Анталья"}',
    }
    assert tool_msg["role"] == "tool" and tool_msg["tool_call_id"] == "c1"
    assert json.loads(tool_msg["content"]) == {"city": "Анталья", "sea_c": 26}


def test_should_run_every_tool_call_of_one_round():
    llm = FakeLLM(
        rounds=[
            [call("get_weather", '{"city": "Сочи"}', "a"), call("get_weather", '{"city": "Дубай"}', "b")],
            ["Готово"],
        ]
    )

    events = run(llm, registry())

    assert [e["args"]["city"] for e in events if e["type"] == "tool_start"] == ["Сочи", "Дубай"]
    assert [m["tool_call_id"] for m in llm.conversations[1] if m["role"] == "tool"] == ["a", "b"]


def test_should_report_invalid_arguments_to_the_model_and_keep_going():
    llm = FakeLLM(rounds=[[call("get_weather", '{"town": "Сочи"}')], ["Уточню город."]])

    events = run(llm, registry())

    end = next(e for e in events if e["type"] == "tool_end")
    assert end["ok"] is False
    error = json.loads(llm.conversations[1][-1]["content"])["error"]
    assert "city" in error
    assert text_of(events) == "Уточню город."


def test_should_report_malformed_json_and_unknown_tools_without_crashing():
    llm = FakeLLM(rounds=[[call("get_weather", "{not json", "a"), call("teleport", "{}", "b")], ["Ок"]])

    events = run(llm, registry())

    assert [e["ok"] for e in events if e["type"] == "tool_end"] == [False, False]
    assert [e["args"] for e in events if e["type"] == "tool_start"] == [{}, {}]
    assert text_of(events) == "Ок"


def test_should_hide_tool_exception_details_from_user_and_model():
    llm = FakeLLM(rounds=[[call("broken", '{"city": "Сочи"}')], ["Не получилось."]])

    events = run(llm, registry())

    assert "hunter2" not in json.dumps(events, ensure_ascii=False)
    assert "hunter2" not in json.dumps(llm.calls, ensure_ascii=False)


def test_should_separate_text_from_different_rounds():
    llm = FakeLLM(rounds=[["Смотрю погоду.", call("get_weather", '{"city": "Сочи"}')], ["Тепло."]])

    events = run(llm, registry())

    assert text_of(events) == "Смотрю погоду.\n\nТепло."
    assert llm.conversations[1][-2]["content"] == "Смотрю погоду."


def test_should_force_a_final_answer_without_tools_after_the_round_limit():
    looping = [[call("get_weather", '{"city": "Сочи"}', f"c{i}")] for i in range(agent.MAX_TOOL_ROUNDS)]
    llm = FakeLLM(rounds=[*looping, ["Вот что нашёл."]])

    events = run(llm, registry())

    assert sum(e["type"] == "tool_start" for e in events) == agent.MAX_TOOL_ROUNDS
    assert len(llm.calls) == agent.MAX_TOOL_ROUNDS + 1
    assert llm.tools_seen[-1] is None
    assert llm.calls[-1][-2]["content"] == agent.STEP_LIMIT_NOTE  # then the reply checklist
    assert text_of(events) == "Вот что нашёл."


def test_should_remind_the_model_to_answer_in_english_on_every_call():
    llm = FakeLLM(rounds=[[call("get_weather", '{"city": "Sochi"}')], ["Warm."]])

    run(llm, registry(), query="Beach trip in November with my kid, cheap")

    assert all(c[-1] == {"role": "system", "content": agent.ENGLISH_NOTE} for c in llm.calls)
    assert [m["role"] for m in llm.calls[0][-2:]] == ["user", "system"]
    roles_after_tools = [m["role"] for m in llm.calls[1][-3:]]
    assert roles_after_tools == ["tool", "system", "system"]  # the reminders come after the tool results


def test_should_repeat_the_reply_checklist_once_tool_results_are_in():
    llm = FakeLLM(rounds=[[call("get_weather", '{"city": "Сочи"}')], ["Тепло."]])

    run(llm, registry())

    checklist = {"role": "system", "content": agent.REPLY_CHECKLIST}
    assert checklist not in llm.calls[0]  # before any tool ran, it would push the model to answer at once
    assert llm.calls[1][-1] == checklist and llm.conversations[1][-1]["role"] == "tool"


def test_should_not_add_the_english_reminder_to_russian_or_mixed_messages():
    for query in ["Хочу к морю", "Хочу в Dubai"]:
        llm = FakeLLM()
        run(llm, query=query)
        assert all(m.get("content") != agent.ENGLISH_NOTE for m in llm.calls[0])
