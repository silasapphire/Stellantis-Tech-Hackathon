from __future__ import annotations

from typing import Awaitable, Callable

from mcp import ClientSession

from agents.graph.activity_log import make_activity_hook
from agents.graph.groq_tool_loop import run_tool_loop
from agents.graph.state import GraphState

SYSTEM_PROMPT = (
    "You are the diagnostic agent for a connected-vehicle monitoring platform. "
    "Call diagnostics_detect_anomaly with the given asset_id to check for anomalies against "
    "both the fault-library thresholds and ML outlier detection. If it reports any findings, "
    "write ONE clear paragraph explaining what's wrong in plain language for a fleet operator, "
    "referencing the specific metric(s) and values involved. If there are no findings, reply "
    "with exactly: no anomaly detected."
)


def build_diagnose_node(session: ClientSession) -> Callable[[GraphState], Awaitable[dict]]:
    async def diagnose_node(state: GraphState) -> dict:
        asset_id = state["asset_id"]
        calls: list[dict] = []

        answer, transcript = await run_tool_loop(
            session,
            SYSTEM_PROMPT,
            f"asset_id: {asset_id}",
            max_turns=3,
            on_tool_result=make_activity_hook(asset_id, "diagnostic", calls),
        )

        detect_result = next(
            (t["result"] for t in transcript if t["tool"] == "diagnostics_detect_anomaly"),
            {"findings": [], "issues": []},
        )
        findings = detect_result.get("findings", []) if isinstance(detect_result, dict) else []
        issues = detect_result.get("issues", []) if isinstance(detect_result, dict) else []
        tool_calls = state.get("tool_calls", []) + calls

        if not findings:
            return {"findings": [], "issue": None, "outcome": "no_anomaly", "tool_calls": tool_calls}

        return {
            "findings": findings,
            "issue": issues[0] if issues else None,
            "explanation": answer,
            "outcome": "anomaly_found",
            "tool_calls": tool_calls,
        }

    return diagnose_node
