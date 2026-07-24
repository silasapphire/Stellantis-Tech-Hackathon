from __future__ import annotations

from typing import Awaitable, Callable

from mcp import ClientSession

from agents.graph.groq_tool_loop import run_tool_loop
from agents.graph.state import GraphState

SYSTEM_PROMPT = (
    "You are the self-healing agent for a connected-vehicle monitoring platform. Given an "
    "issue's type and explanation, choose exactly one remediation action from: throttle_load, "
    "eco_mode, restart_subsystem, schedule_service - and call actions_trigger_self_heal with the "
    "asset_id and your chosen action. Prefer throttle_load, eco_mode, or restart_subsystem for "
    "acute thermal, pressure, or vibration conditions that can plausibly clear by reducing load "
    "or resetting a subsystem. Use schedule_service for degradation-type conditions (capacity/SOH "
    "loss, cumulative wear) that a mode switch cannot fix. After calling the tool, reply with one "
    "short sentence confirming the action taken."
)


def build_self_heal_node(session: ClientSession) -> Callable[[GraphState], Awaitable[dict]]:
    async def self_heal_node(state: GraphState) -> dict:
        asset_id = state["asset_id"]
        issue = state.get("issue") or {}
        calls: list[dict] = []

        def record(name: str, args: dict) -> None:
            calls.append({"node": "self_healing", "tool": name, "args": args})

        user_prompt = (
            f"asset_id: {asset_id}\n"
            f"issue_type: {issue.get('type')}\n"
            f"explanation: {state.get('explanation', '')}"
        )
        _, transcript = await run_tool_loop(session, SYSTEM_PROMPT, user_prompt, max_turns=3, on_tool_call=record)

        heal_result = next((t["result"] for t in transcript if t["tool"] == "actions_trigger_self_heal"), None)
        action = heal_result.get("action") if isinstance(heal_result, dict) else None
        effective = heal_result.get("effective") if isinstance(heal_result, dict) else None

        return {
            "self_heal_action": action,
            "self_heal_effective": effective,
            "outcome": "self_healed",
            "tool_calls": state.get("tool_calls", []) + calls,
        }

    return self_heal_node
