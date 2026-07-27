"""Shared ReAct-style loop: Groq picks MCP tools to call (via OpenAI-compatible
tool-calling), we execute them against the shared MCP session and feed results
back, until Groq returns a final text answer. Every graph node - and the
conversational orchestrator - reuses this instead of hand-coding its own
tool-call sequence.
"""
from __future__ import annotations

import asyncio
import inspect
import json
import os
from typing import Any, Awaitable, Callable

import groq
from groq import Groq
from mcp import ClientSession

from agents.graph.mcp_tools import call_mcp_tool, list_groq_tools

GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
_COMPLETION_RETRIES = 3

ToolCallHook = Callable[[str, dict[str, Any]], Awaitable[None] | None]
ToolResultHook = Callable[[str, dict[str, Any], Any], Awaitable[None] | None]


async def run_tool_loop(
    session: ClientSession,
    system_prompt: str,
    user_prompt: str,
    max_turns: int = 6,
    on_tool_call: ToolCallHook | None = None,
    on_tool_result: ToolResultHook | None = None,
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
        message = await _complete_with_retry(client, messages, tools)
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
            if on_tool_result:
                maybe_awaitable = on_tool_result(name, args, result)
                if inspect.isawaitable(maybe_awaitable):
                    await maybe_awaitable
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


async def _complete_with_retry(client: Groq, messages: list[dict], tools: list[dict]):
    """Groq's Llama tool-calling occasionally emits a malformed function-call
    token and 400s with `tool_use_failed` - transient, and a bare retry of the
    same request normally succeeds. Also covers rate limits/5xx. Runs the
    (blocking) SDK call off the event loop so it doesn't stall the scheduler
    or concurrent chat connections sharing this process.
    """
    last_error: Exception | None = None
    for attempt in range(_COMPLETION_RETRIES):
        try:
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model=GROQ_MODEL,
                messages=messages,
                tools=tools,
                tool_choice="auto",
            )
            return response.choices[0].message
        except (groq.APIStatusError, groq.APIConnectionError) as exc:
            last_error = exc
            if attempt < _COMPLETION_RETRIES - 1:
                await asyncio.sleep(0.5 * (attempt + 1))
    raise last_error
