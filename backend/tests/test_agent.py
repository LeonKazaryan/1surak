import asyncio
import json
from datetime import datetime

from pydantic import BaseModel

from app import agent
from app.llm import ToolCall, ToolStarting
from app.tools import Tool, ToolRegistry, ToolReply
from tests.conftest import FakeLLM

FIXED_NOW = datetime(2026, 10, 24, 12, 0, tzinfo=agent.MSK)


class CityArgs(BaseModel):
    city: str


async def _weather(args: CityArgs) -> dict:
    return {"city": args.city, "sea_c": 26}


async def _broken(args: CityArgs) -> dict:
    raise RuntimeError("db password is hunter2")


async def _ask(args: CityArgs) -> ToolReply:
    return ToolReply(
        result={"asked": True},
        text="Уточню одно",
        event={"type": "clarify", "questions": [{"slot": "when"}]},
        ends_turn=True,
    )


def registry() -> ToolRegistry:
    return ToolRegistry(
        [
            Tool(name="ask", title="Спрашиваю", description="Ask the user", args=CityArgs, handler=_ask),
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

    assert [t["function"]["name"] for t in llm.tools_seen[0]] == ["ask", "get_weather", "broken"]
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


def test_should_turn_short_text_before_tool_calls_into_a_step_not_the_answer():
    llm = FakeLLM(rounds=[["Смотрю погоду.", call("get_weather", '{"city": "Сочи"}')], ["Тепло."]])

    events = run(llm, registry())

    assert events[0] == {"type": "assistant_note", "text": "Смотрю погоду."}
    assert text_of(events) == "Тепло."
    assert llm.conversations[1][-2]["content"] == "Смотрю погоду."


def test_should_stream_long_text_live_even_when_tools_follow():
    long = "Сначала расскажу подробно. " * 12
    llm = FakeLLM(rounds=[[long, call("get_weather", '{"city": "Сочи"}')], ["Тепло."]])

    events = run(llm, registry())

    assert events[0]["type"] == "assistant_token"
    assert text_of(events) == f"{long}\n\nТепло."


def test_should_drop_text_that_repeats_a_tool_argument():
    args = '{"city": "Сочи, у моря"}'
    llm = FakeLLM(rounds=[["Сочи,  у моря", call("get_weather", args)], ["Ок"]])

    events = run(llm, registry())

    assert not any(e["type"] == "assistant_note" for e in events)


class IntroArgs(BaseModel):
    intro: str


async def _show(args: IntroArgs) -> ToolReply:
    return ToolReply(result={"shown": True}, text=args.intro, event={"type": "trip_plan"}, ends_turn=True)


def test_should_say_a_long_intro_once_when_the_tool_shows_it_too():
    intro = "Собрал поездку и всё проверил по билетам и отелю. " * 8
    show = Tool(name="show", title="Показываю план", description="Show", args=IntroArgs, handler=_show)
    llm = FakeLLM(rounds=[[intro, call("show", json.dumps({"intro": intro}, ensure_ascii=False))]])

    events = run(llm, ToolRegistry([show]))

    assert text_of(events) == intro


def test_should_say_the_reply_once_when_the_intro_says_it_again_in_other_words():
    said = (
        "Собрал Нячанг на двоих. Отель Luxury Nha Trang Hotel настоящий, трёхзвёздочный и в центре, цена "
        "ориентировочная, условия уточним при бронировании. Прилёт в 04:25, в отеле будете около 05:15, а заселение "
        "обычно с 14:00, предупредим о раннем заезде. Если хочется дешевле, есть хостел в центре."
    )
    intro = (
        "Собрал Нячанг на двоих с 7 по 16 ноября, 9 ночей. Отель Luxury Nha Trang Hotel настоящий, 3 звезды и в "
        "центре, цена ориентировочная, условия уточним при бронировании. Прилёт в 04:25, заселение обычно с 14:00, "
        "в отеле будете около 05:15, предупредим отель о раннем заезде. Если нужен вариант дешевле, есть хостел."
    )
    show = Tool(name="show", title="Показываю план", description="Show", args=IntroArgs, handler=_show)
    llm = FakeLLM(rounds=[[said, call("show", json.dumps({"intro": intro}, ensure_ascii=False))]])

    events = run(llm, ToolRegistry([show]))

    assert text_of(events) == said  # the streamed answer stays, its near copy is not added


def test_should_say_the_reply_once_when_the_owed_call_repeats_it_in_the_next_round():
    said = "Собрал Нячанг под вашу семью: отель в центре, три звезды, прилёт к восьми утра. " * 5
    intro = "Собрал Нячанг для вас с ребёнком: отель в центре, три звезды, прилёт к восьми утра. " * 5
    build = Tool(
        name="build", title="Собираю", description="Build", args=IntroArgs, handler=_built, then="show"
    )
    show = Tool(name="show", title="Показываю план", description="Show", args=IntroArgs, handler=_show)
    llm = FakeLLM(
        rounds=[
            [call("build", '{"intro": ""}')],
            [said],  # the reply in words while the plan is still owed
            # the next round makes the call and writes the reply once more besides
            [intro, call("show", json.dumps({"intro": intro}, ensure_ascii=False))],
        ]
    )

    events = run(llm, ToolRegistry([build, show]))

    assert text_of(events) == said
    assert any(e["type"] == "trip_plan" for e in events)


async def _built(args: IntroArgs) -> dict:
    return {"built": True}


def test_should_say_which_tool_is_coming_while_its_arguments_are_written():
    show = Tool(name="show", title="Показываю план", description="Show", args=IntroArgs, handler=_show)
    llm = FakeLLM(rounds=[[ToolStarting("show"), call("show", '{"intro": "Готово"}')]])

    events = run(llm, ToolRegistry([show]))

    kinds = [e["type"] for e in events]
    assert kinds.index("tool_preparing") < kinds.index("tool_start")
    assert next(e for e in events if e["type"] == "tool_preparing") == {
        "type": "tool_preparing",
        "name": "show",
        "title": "Показываю план",
    }


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


def test_should_show_a_tool_widget_with_its_text_and_hand_the_turn_back():
    llm = FakeLLM(
        rounds=[[call("get_weather", '{"city": "Сочи"}', "a"), call("ask", '{"city": "Сочи"}', "b")]]
    )

    events = run(llm, registry())

    assert [e["type"] for e in events] == [
        "tool_start",
        "tool_end",
        "tool_start",
        "tool_end",
        "assistant_token",
        "clarify",
    ]
    assert text_of(events) == "Уточню одно"
    assert events[-1] == {"type": "clarify", "questions": [{"slot": "when"}]}
    assert len(llm.calls) == 1  # the model is not called again: the user answers next


def _search_then_show() -> ToolRegistry:
    search = Tool(
        name="search", title="Ищу", description="Find", args=CityArgs, handler=_weather, then="show"
    )
    return ToolRegistry(
        [search, Tool(name="show", title="Показываю", description="Show", args=CityArgs, handler=_ask)]
    )


def test_should_make_the_model_show_what_it_found_instead_of_listing_it():
    llm = FakeLLM(
        rounds=[
            [call("search", '{"city": "Сочи"}', "a")],
            ["Подходят Сочи и Анапа."],
            [call("show", '{"city": "Сочи"}', "b")],
        ]
    )

    events = run(llm, _search_then_show())

    assert llm.tool_choices == [None, None, "show"]
    assert {"type": "assistant_note", "text": "Подходят Сочи и Анапа."} in events
    assert text_of(events) == "Уточню одно"  # the words came from the shown cards, not the list
    assert events[-1]["type"] == "clarify"


def test_should_insist_on_showing_only_once():
    llm = FakeLLM(rounds=[[call("search", '{"city": "Сочи"}')], ["Подходят Сочи."], ["Всё равно текстом."]])

    events = run(llm, _search_then_show())

    assert llm.tool_choices == [None, None, "show"]
    assert text_of(events) == "Всё равно текстом."


def test_should_not_insist_when_the_follow_up_tool_is_not_registered():
    search = Tool(
        name="search", title="Ищу", description="Find", args=CityArgs, handler=_weather, then="show"
    )
    llm = FakeLLM(rounds=[[call("search", '{"city": "Сочи"}')], ["Подходят Сочи."]])

    events = run(llm, ToolRegistry([search]))

    assert llm.tool_choices == [None, None]
    assert text_of(events) == "Подходят Сочи."


def test_should_end_the_turn_with_the_tokens_of_every_model_call():
    from app.llm import Usage

    llm = FakeLLM(
        rounds=[
            [ToolCall(id="c1", name="get_weather", arguments='{"city": "Сочи"}'), Usage(1000, 20, 800)],
            ["Тепло", Usage(1200, 30, 1000)],
        ]
    )

    events = run(llm, registry())

    assert events[-1] == {
        "type": "usage",
        "llm_calls": 2,
        "input_tokens": 2200,
        "cached_tokens": 1800,
        "output_tokens": 50,
    }
