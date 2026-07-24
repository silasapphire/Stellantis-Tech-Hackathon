from __future__ import annotations

from typing import Any, TypedDict


class ToolCallRecord(TypedDict):
    node: str
    tool: str
    args: dict[str, Any]


class GraphState(TypedDict, total=False):
    asset_id: str

    findings: list[dict]
    issue: dict | None
    explanation: str
    prediction: dict | None
    recommendation: str

    self_heal_action: str | None
    self_heal_effective: bool | None

    outcome: str  # "no_anomaly" | "monitoring" | "resolved" | "escalated" | "self_healed"
    tool_calls: list[ToolCallRecord]  # transcript for the transparency UI
