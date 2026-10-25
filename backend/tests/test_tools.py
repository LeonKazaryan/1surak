import asyncio
import json

import pytest
from pydantic import BaseModel

from app.tools import Tool, ToolRegistry
from app.tools import registry as registry_module


class NoArgs(BaseModel):
    pass


async def _ok(_: NoArgs) -> dict:
    return {"answer": 42}


def tool(name: str = "answer", handler=_ok, **kwargs) -> Tool:
    return Tool(name=name, title="Считаю", description="The answer", args=NoArgs, handler=handler, **kwargs)


def test_should_describe_tools_in_openai_function_format():
    spec = ToolRegistry([tool()]).specs()[0]

    assert spec["type"] == "function"
    assert spec["function"]["name"] == "answer"
    assert spec["function"]["parameters"]["type"] == "object"


def test_should_refuse_duplicate_tool_names():
    with pytest.raises(ValueError):
        ToolRegistry([tool(), tool()])


def test_should_return_result_as_json_with_a_short_preview():
    registry = ToolRegistry([tool(preview=lambda r: "ответ " * 100)])

    result = asyncio.run(registry.execute("answer", ""))

    assert result.ok
    assert json.loads(result.content) == {"answer": 42}
    assert len(result.preview) <= registry_module.PREVIEW_MAX_CHARS


def test_should_time_out_slow_tools(monkeypatch):
    monkeypatch.setattr(registry_module, "TOOL_TIMEOUT_S", 0.01)

    async def slow(_: NoArgs) -> dict:
        await asyncio.sleep(1)
        return {}

    result = asyncio.run(ToolRegistry([tool(handler=slow)]).execute("answer", "{}"))

    assert not result.ok
    assert "timed out" in json.loads(result.content)["error"]


def test_should_reject_non_object_arguments():
    result = asyncio.run(ToolRegistry([tool()]).execute("answer", "[1, 2]"))

    assert not result.ok
