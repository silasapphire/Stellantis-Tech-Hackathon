"""The conversational orchestrator: user-facing chat, backed by the same Groq
tool loop as every other agent, but with access to every tool on the MCP
server (not a restricted subset) and a longer tool-call budget so it can chain
multiple lookups per turn.
"""
from __future__ import annotations

from mcp import ClientSession

from agents.graph.activity_log import make_activity_hook
from agents.graph.groq_tool_loop import ToolCallHook, run_tool_loop

SYSTEM_PROMPT = (
    "You are the conversational assistant for a Smart Connected Diagnostics Platform. You have "
    "tools to inspect telemetry, digital twin state, issue history, and repair guidance, and to "
    "trigger self-heal actions or notifications. The user is currently looking at asset_id: "
    "{asset_id}. Use tools to ground every factual claim - cite concrete numbers from tool "
    "results rather than guessing. If asked to fix, resolve, or heal something, call "
    "actions_trigger_self_heal with a plausible action (throttle_load, eco_mode, "
    "restart_subsystem, or schedule_service) for that asset's current open issue. Be concise: "
    "2-4 sentences unless the user asks for more detail."
)


async def run_conversation_turn(
    session: ClientSession,
    asset_id: str,
    user_message: str,
    history: list[dict[str, str]] | None = None,
    on_tool_call: ToolCallHook | None = None,
    max_turns: int = 6,
) -> tuple[str, list[dict]]:
    system_prompt = SYSTEM_PROMPT.format(asset_id=asset_id)
    return await run_tool_loop(
        session,
        system_prompt,
        user_message,
        max_turns=max_turns,
        on_tool_call=on_tool_call,
        on_tool_result=make_activity_hook(asset_id, "conversational", []),
        history=history,
    )
