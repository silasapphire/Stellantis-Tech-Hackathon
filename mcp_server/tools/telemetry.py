from __future__ import annotations

import uuid
from datetime import datetime

from mcp.server.fastmcp import FastMCP

from common.firestore_client import COLLECTIONS, get_firestore_client
from mcp_server.tools._firestore_helpers import get_asset, get_recent_readings


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def telemetry_get_latest(asset_id: str) -> dict:
        """Get the most recent telemetry reading for an asset."""
        readings = get_recent_readings(asset_id, limit=1)
        if not readings:
            raise ValueError(f"no telemetry for asset_id: {asset_id}")
        return readings[0]

    @mcp.tool()
    def telemetry_get_history(asset_id: str, limit: int = 100) -> list[dict]:
        """Get recent telemetry history for an asset, newest first."""
        return get_recent_readings(asset_id, limit=limit)

    @mcp.tool()
    def telemetry_get_asset_metadata(asset_id: str) -> dict:
        """Get asset metadata, including vehicle_type, so twin selection is tool-driven."""
        return get_asset(asset_id)

    @mcp.tool()
    def telemetry_record_sustainability_period(
        asset_id: str,
        period_start: str,
        period_end: str,
        energy_or_fuel_used: float,
        estimated_co2: float,
        baseline_co2: float,
    ) -> dict:
        """Persist a sustainability comparison period (actual vs a no-AI-optimization baseline) for an asset."""
        db = get_firestore_client()
        period_id = str(uuid.uuid4())
        db.collection(COLLECTIONS.SUSTAINABILITY).document(asset_id).collection("periods").document(period_id).set(
            {
                "period_start": datetime.fromisoformat(period_start),
                "period_end": datetime.fromisoformat(period_end),
                "energy_or_fuel_used": energy_or_fuel_used,
                "estimated_co2": estimated_co2,
                "baseline_co2": baseline_co2,
            }
        )
        return {"period_id": period_id, "status": "recorded"}
