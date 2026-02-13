"""Tool-calling helpers compatible with OpenAI/Anthropic style schemas."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Mapping


@dataclass
class Tool:
    name: str
    description: str
    parameters: Mapping[str, Any]
    handler: Callable[[Mapping[str, Any]], Any] | Callable[[Mapping[str, Any]], Awaitable[Any]]


def to_openai_tool(tool: Tool) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": dict(tool.parameters),
        },
    }


def to_anthropic_tool(tool: Tool) -> dict[str, Any]:
    return {
        "name": tool.name,
        "description": tool.description,
        "input_schema": dict(tool.parameters),
    }


def to_generic_tool(tool: Tool) -> dict[str, Any]:
    return {
        "name": tool.name,
        "description": tool.description,
        "parameters": dict(tool.parameters),
    }


async def dispatch_tool_call(
    tool_map: Mapping[str, Tool],
    tool_call: Mapping[str, Any],
) -> Any:
    name, args = _parse_tool_call(tool_call)
    if name not in tool_map:
        raise KeyError(f"unknown tool: {name}")
    handler = tool_map[name].handler
    result = handler(args)
    if asyncio.iscoroutine(result):
        return await result
    return result


def dispatch_tool_call_sync(
    tool_map: Mapping[str, Tool],
    tool_call: Mapping[str, Any],
) -> Any:
    result = dispatch_tool_call(tool_map, tool_call)
    if asyncio.iscoroutine(result):
        return asyncio.run(result)
    return result


def _parse_tool_call(tool_call: Mapping[str, Any]) -> tuple[str, Mapping[str, Any]]:
    if tool_call.get("type") == "function" and isinstance(tool_call.get("function"), Mapping):
        function = tool_call["function"]
        name = function.get("name")
        raw_args = function.get("arguments", {})
    else:
        name = tool_call.get("name")
        raw_args = tool_call.get("arguments", tool_call.get("input", {}))

    if not isinstance(name, str):
        raise ValueError("tool name missing")

    if isinstance(raw_args, str):
        try:
            raw_args = json.loads(raw_args)
        except json.JSONDecodeError:
            raise ValueError("tool arguments must be JSON") from None

    if not isinstance(raw_args, Mapping):
        raise ValueError("tool arguments must be object")

    return name, raw_args
