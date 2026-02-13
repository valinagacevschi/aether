from __future__ import annotations

import asyncio

from aether.tools import Tool, dispatch_tool_call, to_anthropic_tool, to_generic_tool, to_openai_tool


def test_tool_adapters() -> None:
    tool = Tool(
        name="ping",
        description="Ping",
        parameters={"type": "object", "properties": {"value": {"type": "string"}}},
        handler=lambda args: args,
    )
    assert to_openai_tool(tool)["function"]["name"] == "ping"
    assert to_anthropic_tool(tool)["name"] == "ping"
    assert to_generic_tool(tool)["name"] == "ping"


def test_dispatch_tool_call_openai() -> None:
    tool = Tool(
        name="echo",
        description="Echo",
        parameters={"type": "object", "properties": {"text": {"type": "string"}}},
        handler=lambda args: args["text"],
    )
    call = {"type": "function", "function": {"name": "echo", "arguments": "{\"text\":\"hi\"}"}}
    result = asyncio.run(dispatch_tool_call({"echo": tool}, call))
    assert result == "hi"
