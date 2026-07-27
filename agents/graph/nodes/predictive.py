from __future__ import annotations

from typing import Awaitable, Callable

from mcp import ClientSession

from agents.graph.activity_log import make_activity_hook
from agents.graph.groq_tool_loop import run_tool_loop
from agents.graph.state import GraphState

SYSTEM_PROMPT = (
    "You are the predictive-maintenance agent for a connected-vehicle monitoring platform. "
    "Call twin_predict_failure with the given asset_id and horizon_days=30 to forecast failure "
    "risk. The tool call itself persists the risk score onto the asset record - you do not need "
    "to do anything else. Reply with one short sentence summarizing the risk level."
)


def build_predict_node(session: ClientSession) -> Callable[[GraphState], Awaitable[dict]]:
    async def predict_node(state: GraphState) -> dict:
        asset_id = state["asset_id"]
        calls: list[dict] = []

        _, transcript = await run_tool_loop(
            session,
            SYSTEM_PROMPT,
            f"asset_id: {asset_id}",
            max_turns=2,
            on_tool_result=make_activity_hook(asset_id, "predictive", calls),
        )
        prediction = next((t["result"] for t in transcript if t["tool"] == "twin_predict_failure"), None)

        return {"prediction": prediction, "tool_calls": state.get("tool_calls", []) + calls}

    return predict_node
