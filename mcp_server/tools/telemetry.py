from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp_server.tools._store_helpers import get_asset, get_recent_readings


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
