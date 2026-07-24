"""Bridges MCP tool schemas <-> Groq's OpenAI-compatible function-calling format,
and executes MCP tool calls, extracting FastMCP's structured (or JSON-text) result.
"""
from __future__ import annotations

import json
from typing import Any

from mcp import ClientSession


async def list_groq_tools(session: ClientSession) -> list[dict]:
    result = await session.list_tools()
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": tool.inputSchema,
            },
        }
        for tool in result.tools
    ]


async def call_mcp_tool(session: ClientSession, name: str, arguments: dict[str, Any]) -> Any:
    result = await session.call_tool(name, arguments)
    if result.isError:
        message = "; ".join(getattr(block, "text", str(block)) for block in result.content)
        raise RuntimeError(f"MCP tool '{name}' failed: {message}")

    if result.structuredContent is not None:
        # FastMCP wraps non-object returns (e.g. a bare list) under a "result" key.
        if isinstance(result.structuredContent, dict) and set(result.structuredContent) == {"result"}:
            return result.structuredContent["result"]
        return result.structuredContent

    for block in result.content:
        if block.type == "text":
            try:
                return json.loads(block.text)
            except json.JSONDecodeError:
                return block.text
    return None
