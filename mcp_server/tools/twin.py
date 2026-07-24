from __future__ import annotations

import uuid
from datetime import datetime, timezone

from mcp.server.fastmcp import FastMCP

from common.firestore_client import COLLECTIONS, get_firestore_client
from mcp_server.tools._twin_client import call_twin_service


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def twin_get_state(asset_id: str) -> dict:
        """Get the current modeled digital twin state for an asset (thresholds + findings included)."""
        return call_twin_service(asset_id, "state")

    @mcp.tool()
    def twin_simulate(asset_id: str, hypothetical_params: dict, horizon_days: int = 30) -> dict:
        """Run the twin forward under hypothetical operating conditions (e.g. {"daily_cycle_rate": 1.5})."""
        return call_twin_service(
            asset_id, "simulate", {"hypothetical_params": hypothetical_params, "horizon_days": horizon_days}
        )

    @mcp.tool()
    def twin_predict_failure(asset_id: str, horizon_days: int = 30) -> dict:
        """Forecast failure risk and horizon for an asset; also persists the risk score onto the asset and a twin_snapshots record."""
        prediction = call_twin_service(asset_id, "predict", {"horizon_days": horizon_days})
        _persist_prediction(asset_id, prediction)
        return prediction


def _persist_prediction(asset_id: str, prediction: dict) -> None:
    db = get_firestore_client()
    now = datetime.now(timezone.utc)

    db.collection(COLLECTIONS.ASSETS).document(asset_id).update(
        {
            "risk_score": prediction["risk_score"],
            "risk_score_numeric": prediction["risk_score_numeric"],
        }
    )

    snapshot_id = str(uuid.uuid4())
    db.collection(COLLECTIONS.TWIN_SNAPSHOTS).document(asset_id).collection("snapshots").document(snapshot_id).set(
        {
            "timestamp": now,
            "modeled_state": prediction,
            "predicted_failure_horizon_days": prediction.get("predicted_failure_horizon_days"),
        }
    )
