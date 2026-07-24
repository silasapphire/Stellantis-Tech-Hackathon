from __future__ import annotations

from typing import Awaitable, Callable

from mcp import ClientSession

from agents.graph.groq_tool_loop import run_tool_loop
from agents.graph.state import GraphState

SYSTEM_PROMPT = (
    "You are the sustainability agent for a connected-vehicle monitoring platform. Call "
    "telemetry_get_history for the given asset_id (limit=200) and twin_get_state to review "
    "recent energy usage (charge_rate for an EV) or fuel usage (fuel_rate for an ICE vehicle). "
    "Estimate: energy_or_fuel_used over the window (kWh for EV, liters for ICE), estimated_co2 "
    "in kg for that usage, and baseline_co2 in kg - what CO2 would have been emitted over the "
    "same window WITHOUT this platform's self-healing/throttling optimizations (assume "
    "baseline_co2 is modestly higher, in the 10-20% range, reflecting avoided wasteful "
    "operation). Then call telemetry_record_sustainability_period with asset_id, period_start "
    "and period_end as ISO-8601 timestamps spanning the reviewed window, and your three "
    "estimates. Reply with one short sentence summarizing the comparison."
)


def build_sustainability_node(session: ClientSession) -> Callable[[GraphState], Awaitable[dict]]:
    async def sustainability_node(state: GraphState) -> dict:
        asset_id = state["asset_id"]
        calls: list[dict] = []

        def record(name: str, args: dict) -> None:
            calls.append({"node": "sustainability", "tool": name, "args": args})

        answer, transcript = await run_tool_loop(
            session, SYSTEM_PROMPT, f"asset_id: {asset_id}", max_turns=4, on_tool_call=record
        )
        recorded = next(
            (t["result"] for t in transcript if t["tool"] == "telemetry_record_sustainability_period"), None
        )

        return {"outcome": "sustainability_recorded", "tool_calls": state.get("tool_calls", []) + calls, "_summary": answer, "_recorded": recorded}

    return sustainability_node
