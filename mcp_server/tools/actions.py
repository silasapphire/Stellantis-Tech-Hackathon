"""Self-heal actions are scoped to what's plausible for a connected vehicle asset:
throttling, mode switches, subsystem resets, and service scheduling - never literal
physical repair.

`throttle_load`/`eco_mode`/`restart_subsystem` can only clear a *demo-injected* fault
(the simulator's optional fault overlay). The platform replays real recorded data, so
against a genuine fault in that data (an active DTC, a degraded battery) they change
nothing and the result honestly reports effective=False; the issue then keeps escalating
until a human services the vehicle. `schedule_service` books a service visit and never
touches live telemetry.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import httpx
from mcp.server.fastmcp import FastMCP

from common.store import COLLECTIONS, get_store
from common.schemas import IssueState, NotificationType

_http = httpx.Client(timeout=5.0, trust_env=False)
SIMULATOR_URL = os.environ.get("SIMULATOR_URL", "http://127.0.0.1:8200")

ACTION_CLEARS_LIVE_FAULT = {
    "throttle_load": True,
    "eco_mode": True,
    "restart_subsystem": True,
    "schedule_service": False,
}


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def actions_trigger_self_heal(asset_id: str, action: str) -> dict:
        """Trigger a self-heal action for an asset's most recent open issue: throttle_load, eco_mode, restart_subsystem, or schedule_service."""
        return _trigger_self_heal(asset_id, action)

    @mcp.tool()
    def actions_send_notification(channel: str, message: str, asset_id: str = "", issue_id: str = "") -> dict:
        """Send a human-facing notification (recorded in `notifications`; `channel` is a free-form label like 'dashboard' or 'ops')."""
        return _send_notification(channel, message, asset_id, issue_id)


def _trigger_self_heal(asset_id: str, action: str) -> dict:
    if action not in ACTION_CLEARS_LIVE_FAULT:
        raise ValueError(f"unknown self-heal action: {action}. Expected one of {list(ACTION_CLEARS_LIVE_FAULT)}")

    db = get_store()
    query = (
        db.collection(COLLECTIONS.ISSUES)
        .where("asset_id", "==", asset_id)
        .where("state", "in", [IssueState.OPEN.value, IssueState.MONITORING.value])
        .order_by("detected_at", direction="DESCENDING")
        .limit(1)
    )
    docs = list(query.stream())
    if not docs:
        raise ValueError(f"no open/monitoring issue for asset_id: {asset_id}")

    doc = docs[0]
    issue = doc.to_dict()
    now = datetime.now(timezone.utc)
    attempts = issue.get("self_heal_attempts", 0) + 1
    effective = ACTION_CLEARS_LIVE_FAULT[action]
    if effective:
        try:
            response = _http.delete(f"{SIMULATOR_URL}/simulator/fault/{asset_id}", timeout=5.0)
            effective = bool(response.json().get("cleared")) if response.status_code == 200 else False
        except (httpx.HTTPError, ValueError):
            effective = False  # could not reach the subsystem - do not claim success

    note = f"Self-heal action '{action}' triggered (attempt {attempts})."
    note += " Fault overlay cleared; monitoring for recovery." if effective else " No clearable fault - the underlying condition persists until the vehicle is serviced."

    history_entry = {"state": issue["state"], "timestamp": now, "note": note, "agent": "self_healing"}
    doc.reference.update(
        {
            "self_heal_action": action,
            "self_heal_attempts": attempts,
            "history": issue["history"] + [history_entry],
        }
    )

    _send_notification(
        "dashboard",
        f"Self-heal action '{action}' attempted for asset {asset_id} (attempt {attempts}).",
        asset_id,
        doc.id,
        notif_type=NotificationType.SELF_HEAL,
    )

    return {"issue_id": doc.id, "action": action, "attempt": attempts, "effective": effective}


def _send_notification(
    channel: str, message: str, asset_id: str = "", issue_id: str = "", notif_type: NotificationType = NotificationType.ALERT
) -> dict:
    db = get_store()
    notif_id = str(uuid.uuid4())
    db.collection(COLLECTIONS.NOTIFICATIONS).document(notif_id).set(
        {
            "asset_id": asset_id,
            "issue_id": issue_id,
            "message": f"[{channel}] {message}" if channel and channel != "dashboard" else message,
            "type": notif_type.value,
            "created_at": datetime.now(timezone.utc),
        }
    )
    return {"notification_id": notif_id, "status": "sent"}
