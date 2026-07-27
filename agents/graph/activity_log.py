"""Real-time agent activity log: every MCP tool call any node makes, and its
actual result, is written to Firestore the moment it completes - so the
dashboard shows what each agent genuinely did (not a simulated log).
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from common.firestore_client import COLLECTIONS, get_firestore_client


def make_activity_hook(asset_id: str, agent: str, calls: list[dict]):
    """Returns an on_tool_result-compatible hook (tool, args, result) that
    records locally (for the graph state transcript) and persists to Firestore."""

    async def hook(tool: str, args: dict[str, Any], result: Any) -> None:
        calls.append({"node": agent, "tool": tool, "args": args, "result": result})
        await _record(asset_id, agent, tool, args, result)

    return hook


async def _record(asset_id: str, agent: str, tool: str, args: dict[str, Any], result: Any) -> None:
    summary = _summarize_result(tool, result)

    def _write() -> None:
        db = get_firestore_client()
        db.collection(COLLECTIONS.AGENT_ACTIVITY).add(
            {
                "asset_id": asset_id,
                "agent": agent,
                "tool": tool,
                "args": args,
                "summary": summary,
                "timestamp": datetime.now(timezone.utc),
            }
        )

    await asyncio.to_thread(_write)


def _summarize_result(tool: str, result: Any) -> str:
    if isinstance(result, dict) and "error" in result:
        return f"error: {result['error']}"

    if tool == "diagnostics_detect_anomaly" and isinstance(result, dict):
        findings = result.get("findings", [])
        if not findings:
            return "no anomaly detected"
        return f"{len(findings)} finding(s): " + ", ".join(
            f"{f.get('type')} ({f.get('severity')}, {f.get('confidence', 0) * 100:.0f}% confidence)" for f in findings
        )
    if tool == "twin_predict_failure" and isinstance(result, dict):
        horizon = result.get("predicted_failure_horizon_days")
        horizon_text = f"{horizon:.0f}d to threshold" if horizon is not None else "no near-term threshold crossing"
        return f"risk={result.get('risk_score')} ({result.get('risk_score_numeric', 0):.0f}/100), {horizon_text}"
    if tool == "kb_search_repair_docs" and isinstance(result, list):
        top = result[0].get("fault_type") if result else "n/a"
        return f"{len(result)} doc(s) retrieved, top match: {top}"
    if tool == "diagnostics_update_issue" and isinstance(result, dict):
        return "explanation + recommendation attached to issue"
    if tool == "actions_trigger_self_heal" and isinstance(result, dict):
        return f"action={result.get('action')}, effective={result.get('effective')}, attempt #{result.get('attempt')}"
    if tool == "diagnostics_resolve_if_recovered" and isinstance(result, dict):
        return f"resolved={result.get('resolved')}, state={result.get('state')}"
    if tool == "telemetry_record_sustainability_period" and isinstance(result, dict):
        return "sustainability period recorded"
    return "ok"
