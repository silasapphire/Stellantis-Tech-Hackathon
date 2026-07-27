from __future__ import annotations

from typing import Awaitable, Callable

from mcp import ClientSession

from agents.graph.activity_log import make_activity_hook
from agents.graph.groq_tool_loop import run_tool_loop
from agents.graph.state import GraphState

SYSTEM_PROMPT = (
    "You are the recommendation step of the diagnostic pipeline for a connected-vehicle "
    "monitoring platform. Given a draft issue explanation and predicted risk, call "
    "kb_search_repair_docs with a short query describing the fault to retrieve grounded repair "
    "guidance. Then call diagnostics_update_issue with the issue_id, an explanation (refine the "
    "draft into one clear paragraph, folding in the predicted risk/horizon if given), and a "
    "recommendation grounded in the text kb_search_repair_docs returned - do not invent a "
    "recommendation the retrieved text doesn't support. Reply with a short confirmation once "
    "both tools have been called."
)


def build_recommend_node(session: ClientSession) -> Callable[[GraphState], Awaitable[dict]]:
    async def recommend_node(state: GraphState) -> dict:
        asset_id = state["asset_id"]
        issue = state.get("issue") or {}
        prediction = state.get("prediction") or {}
        calls: list[dict] = []

        user_prompt = (
            f"issue_id: {issue.get('id')}\n"
            f"issue_type: {issue.get('type')}\n"
            f"draft_explanation: {state.get('explanation', '')}\n"
            f"predicted_risk: {prediction.get('risk_score')} "
            f"(horizon {prediction.get('predicted_failure_horizon_days')} days)\n"
        )
        _, transcript = await run_tool_loop(
            session,
            SYSTEM_PROMPT,
            user_prompt,
            max_turns=4,
            on_tool_result=make_activity_hook(asset_id, "recommend", calls),
        )

        update_result = next((t["result"] for t in transcript if t["tool"] == "diagnostics_update_issue"), {})
        recommendation = update_result.get("recommendation", "") if isinstance(update_result, dict) else ""

        return {"recommendation": recommendation, "tool_calls": state.get("tool_calls", []) + calls}

    return recommend_node
