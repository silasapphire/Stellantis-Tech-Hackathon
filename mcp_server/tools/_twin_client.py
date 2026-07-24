"""Shared HTTP client helper for calling the twin service, used by both the
twin_* tools and diagnostics_* tools (which need twin state to evaluate anomalies)."""
from __future__ import annotations

import os

import httpx

from mcp_server.tools._firestore_helpers import get_asset, get_recent_readings

TWIN_SERVICE_URL = os.environ.get("TWIN_SERVICE_URL", "http://localhost:8100")


def call_twin_service(asset_id: str, action: str, extra_body: dict | None = None) -> dict:
    asset = get_asset(asset_id)
    readings = get_recent_readings(asset_id, limit=50)
    if not readings:
        raise ValueError(f"no telemetry for asset_id: {asset_id}; cannot compute twin state")

    body = {"readings": readings, **(extra_body or {})}
    response = httpx.post(
        f"{TWIN_SERVICE_URL}/twin/{asset_id}/{action}",
        params={"vehicle_type": asset["vehicle_type"]},
        json=body,
        timeout=10.0,
    )
    response.raise_for_status()
    return response.json()


def get_twin_state(asset_id: str) -> dict:
    return call_twin_service(asset_id, "state")
