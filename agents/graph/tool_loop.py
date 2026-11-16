"""Shared ReAct-style loop: Cohere (Command model, v2 chat API) picks MCP tools to
call, we execute them against the shared MCP session and feed the results back,
until the model returns a final text answer. Every LangGraph node - and the
conversational orchestrator - reuses this instead of hand-coding its own
tool-call sequence.
"""
from __future__ import annotations

import asyncio
import inspect
import json
import os
from typing import Any, Awaitable, Callable

import cohere
from cohere.core.api_error import ApiError
from mcp import ClientSession

from agents.graph.mcp_tools import call_mcp_tool, list_llm_tools

COHERE_MODEL = os.environ.get("COHERE_MODEL", "command-a-03-2025")
_COMPLETION_RETRIES = 3

ToolCallHook = Callable[[str, dict[str, Any]], Awaitable[None] | None]
ToolResultHook = Callable[[str, dict[str, Any], Any], Awaitable[None] | None]


def get_client() -> cohere.AsyncClientV2:
    key = os.environ.get("COHERE_API_KEY")
    if not key:
        raise RuntimeError("COHERE_API_KEY is not set - add it to .env (see .env.example).")
    return cohere.AsyncClientV2(api_key=key)


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
    client = get_client()
    tools = await list_llm_tools(session)

    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_prompt})
    transcript: list[dict] = []

    for _ in range(max_turns):
        message = await _complete_with_retry(client, messages, tools)

        if not message.tool_calls:
            return _text_of(message), transcript

        messages.append(
            {
                "role": "assistant",
                "tool_plan": message.tool_plan or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments or "{}"},
                    }
                    for tc in message.tool_calls
                ],
            }
        )

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
                    "content": [{"type": "document", "document": {"data": json.dumps(result, default=str)}}],
                }
            )

    return (
        "I wasn't able to finish reasoning about this within the allotted tool-call budget.",
        transcript,
    )


def _text_of(message) -> str:
    parts = getattr(message, "content", None) or []
    return "".join(getattr(p, "text", "") or "" for p in parts)


async def _complete_with_retry(client: cohere.AsyncClientV2, messages: list[dict], tools: list[dict]):
    """Retries rate limits (429), 5xx and transient connection errors with backoff.
    Auth/validation errors are not retried - they won't fix themselves.
    """
    last_error: Exception | None = None
    for attempt in range(_COMPLETION_RETRIES):
        try:
            response = await client.chat(model=COHERE_MODEL, messages=messages, tools=tools, temperature=0.2)
            return response.message
        except ApiError as exc:
            last_error = exc
            retryable = exc.status_code in (429, 500, 502, 503, 504)
            if not retryable or attempt == _COMPLETION_RETRIES - 1:
                raise
            await asyncio.sleep(2.0 * (attempt + 1))
        except Exception as exc:  # network-level (httpx) errors
            last_error = exc
            if attempt == _COMPLETION_RETRIES - 1:
                raise
            await asyncio.sleep(1.0 * (attempt + 1))
    raise last_error  # pragma: no cover
