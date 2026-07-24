"""Shared ReAct-style loop: Groq picks MCP tools to call (via OpenAI-compatible
tool-calling), we execute them against the shared MCP session and feed results
back, until Groq returns a final text answer. Every graph node - and the
conversational orchestrator - reuses this instead of hand-coding its own
tool-call sequence.
"""
from __future__ import annotations

import inspect
import json
import os
from typing import Any, Awaitable, Callable

from groq import Groq
from mcp import ClientSession

from agents.graph.mcp_tools import call_mcp_tool, list_groq_tools

GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

ToolCallHook = Callable[[str, dict[str, Any]], Awaitable[None] | None]


async def run_tool_loop(
    session: ClientSession,
    system_prompt: str,
    user_prompt: str,
    max_turns: int = 6,
    on_tool_call: ToolCallHook | None = None,
    history: list[dict[str, str]] | None = None,
) -> tuple[str, list[dict]]:
    """Runs the loop to completion. Returns (final_text_answer, tool_call_transcript).

    `history` is prior turns (role/content dicts) prepended before the new user
    message, so the conversational orchestrator can carry context across turns.
    """
    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    tools = await list_groq_tools(session)

    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_prompt})
    transcript: list[dict] = []

    for _ in range(max_turns):
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )
        message = response.choices[0].message
        messages.append(message.model_dump(exclude_none=True))

        if not message.tool_calls:
            return message.content or "", transcript

        for tool_call in message.tool_calls:
            name = tool_call.function.name
            args = json.loads(tool_call.function.arguments or "{}")
            if on_tool_call:
                maybe_awaitable = on_tool_call(name, args)
                if inspect.isawaitable(maybe_awaitable):
                    await maybe_awaitable
            try:
                result = await call_mcp_tool(session, name, args)
            except Exception as exc:  # fed back to the model as a tool error, not fatal to the loop
                result = {"error": str(exc)}
            transcript.append({"tool": name, "arguments": args, "result": result})
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result, default=str),
                }
            )

    return (
        "I wasn't able to finish reasoning about this within the allotted tool-call budget.",
        transcript,
    )
