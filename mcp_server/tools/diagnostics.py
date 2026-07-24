"""Rule-based (fault library, via the twin service) + lightweight ML anomaly
detection, and the OPEN -> MONITORING -> RESOLVED auto-recovery check.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import numpy as np
from mcp.server.fastmcp import FastMCP
from sklearn.ensemble import IsolationForest

from common.firestore_client import COLLECTIONS, get_firestore_client
from common.schemas import AssetStatus, IssueState, NotificationType, RiskLevel, Severity
from mcp_server.tools._firestore_helpers import get_recent_readings
from mcp_server.tools._twin_client import get_twin_state

MONITORING_WINDOW_SECONDS = int(os.environ.get("MONITORING_WINDOW_SECONDS", "45"))
SELF_HEAL_ATTEMPT_BUDGET = int(os.environ.get("SELF_HEAL_ATTEMPT_BUDGET", "3"))
ML_ANOMALY_MIN_SAMPLES = 20
ML_NUMERIC_FIELDS = (
    "soc", "soh", "pack_voltage", "cell_temp_spread", "motor_temp", "inverter_temp",
    "rpm", "oil_pressure", "oil_temp", "vibration_index", "fuel_rate",
    "air_fuel_ratio_proxy", "misfire_count", "coolant_temp",
)

_SEVERITY_TO_STATUS = {
    Severity.LOW: AssetStatus.WARNING,
    Severity.MEDIUM: AssetStatus.WARNING,
    Severity.HIGH: AssetStatus.CRITICAL,
}
_SEVERITY_RANK = {Severity.LOW: 1, Severity.MEDIUM: 2, Severity.HIGH: 3}


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def diagnostics_detect_anomaly(asset_id: str) -> dict:
        """Detect anomalies via fault-library thresholds + ML outlier detection; creates/updates `issues` for anything found."""
        return _detect_anomaly(asset_id)

    @mcp.tool()
    def diagnostics_get_issue_history(asset_id: str) -> list[dict]:
        """Get all issues (any state) recorded for an asset, most recently detected first."""
        db = get_firestore_client()
        query = (
            db.collection(COLLECTIONS.ISSUES)
            .where("asset_id", "==", asset_id)
            .order_by("detected_at", direction="DESCENDING")
        )
        return [{"id": doc.id, **doc.to_dict()} for doc in query.stream()]

    @mcp.tool()
    def diagnostics_resolve_if_recovered(issue_id: str) -> dict:
        """Re-check an OPEN/MONITORING issue against fresh telemetry; auto-resolves once metrics stay normal for the monitoring window."""
        return _resolve_if_recovered(issue_id)

    @mcp.tool()
    def diagnostics_update_issue(issue_id: str, explanation: str = "", recommendation: str = "") -> dict:
        """Attach a synthesized explanation and/or a knowledge-base-grounded recommendation to an issue."""
        return _update_issue(issue_id, explanation, recommendation)


def _detect_anomaly(asset_id: str) -> dict:
    db = get_firestore_client()
    twin_state = get_twin_state(asset_id)
    findings = list(twin_state.get("findings", []))
    findings.extend(_ml_anomaly_findings(asset_id, twin_state, existing_types={f["type"] for f in findings}))

    now = datetime.now(timezone.utc)
    created_or_updated: list[dict] = []

    for finding in findings:
        issue = _upsert_issue(db, asset_id, finding, now)
        created_or_updated.append(issue)

    if findings:
        worst = max(findings, key=lambda f: _SEVERITY_RANK[Severity(f["severity"])])
        db.collection(COLLECTIONS.ASSETS).document(asset_id).update(
            {
                "status": _SEVERITY_TO_STATUS[Severity(worst["severity"])].value,
            }
        )

    return {"asset_id": asset_id, "findings": findings, "issues": created_or_updated}


def _ml_anomaly_findings(asset_id: str, twin_state: dict, existing_types: set[str]) -> list[dict]:
    readings = get_recent_readings(asset_id, limit=200)
    if len(readings) < ML_ANOMALY_MIN_SAMPLES:
        return []

    fields = [f for f in ML_NUMERIC_FIELDS if any(r.get(f) is not None for r in readings)]
    if not fields:
        return []

    matrix = np.array([[r.get(f) or 0.0 for f in fields] for r in readings])
    model = IsolationForest(contamination=0.08, random_state=0)
    model.fit(matrix)
    latest_prediction = model.predict(matrix[:1])[0]  # readings are newest-first

    if latest_prediction != -1 or "ml_detected_anomaly" in existing_types:
        return []

    latest_metrics = twin_state.get("metrics", {})
    return [
        {
            "fault_id": f"ml_anomaly_{asset_id}",
            "type": "ml_detected_anomaly",
            "severity": Severity.MEDIUM.value,
            "field": "multivariate",
            "value": 0.0,
            "threshold": 0.0,
            "operator": "isolation_forest",
            "message": (
                "Multivariate outlier detection (IsolationForest over recent telemetry) flagged the "
                f"current reading as anomalous relative to this asset's own recent history: {latest_metrics}."
            ),
        }
    ]


def _upsert_issue(db, asset_id: str, finding: dict, now: datetime) -> dict:
    issues_ref = db.collection(COLLECTIONS.ISSUES)
    existing = list(
        issues_ref.where("asset_id", "==", asset_id)
        .where("type", "==", finding["type"])
        .where("state", "in", [IssueState.NEW.value, IssueState.OPEN.value, IssueState.MONITORING.value])
        .limit(1)
        .stream()
    )

    if existing:
        doc = existing[0]
        data = doc.to_dict()
        if data["state"] == IssueState.MONITORING.value:
            # condition recurred mid-monitoring window - back to OPEN
            history_entry = {
                "state": IssueState.OPEN.value,
                "timestamp": now,
                "note": "Condition recurred during the recovery monitoring window.",
                "agent": "diagnostics",
            }
            doc.reference.update({"state": IssueState.OPEN.value, "history": data["history"] + [history_entry]})
            data["state"] = IssueState.OPEN.value
            data["history"].append(history_entry)
        return {"id": doc.id, **data}

    issue_id = str(uuid.uuid4())
    history_entry = {
        "state": IssueState.OPEN.value,
        "timestamp": now,
        "note": finding["message"],
        "agent": "diagnostics",
    }
    issue = {
        "asset_id": asset_id,
        "type": finding["type"],
        "state": IssueState.OPEN.value,
        "severity": finding["severity"],
        "detected_at": now,
        "resolved_at": None,
        "explanation": finding["message"],
        "recommendation": "",
        "self_heal_action": None,
        "self_heal_attempts": 0,
        "history": [history_entry],
    }
    issues_ref.document(issue_id).set(issue)
    _create_notification(db, asset_id, issue_id, NotificationType.ALERT, finding["message"])
    return {"id": issue_id, **issue}


def _resolve_if_recovered(issue_id: str) -> dict:
    db = get_firestore_client()
    doc = db.collection(COLLECTIONS.ISSUES).document(issue_id).get()
    if not doc.exists:
        raise ValueError(f"unknown issue_id: {issue_id}")

    issue = doc.to_dict()
    if issue["state"] not in (IssueState.OPEN.value, IssueState.MONITORING.value):
        return {"issue_id": issue_id, "resolved": False, "state": issue["state"], "note": "issue is not open/monitoring"}

    twin_state = get_twin_state(issue["asset_id"])
    still_faulted = any(f["type"] == issue["type"] for f in twin_state.get("findings", []))
    now = datetime.now(timezone.utc)

    if still_faulted:
        history = issue["history"]
        if issue["state"] == IssueState.MONITORING.value:
            revert_entry = {
                "state": IssueState.OPEN.value,
                "timestamp": now,
                "note": "Condition recurred during the recovery monitoring window.",
                "agent": "diagnostics",
            }
            history = history + [revert_entry]

        attempts = issue.get("self_heal_attempts", 0)
        if attempts >= SELF_HEAL_ATTEMPT_BUDGET:
            escalate_entry = {
                "state": IssueState.ESCALATED.value,
                "timestamp": now,
                "note": f"Self-heal did not restore normal metrics after {attempts} attempt(s); escalating for human review.",
                "agent": "self_healing",
            }
            doc.reference.update({"state": IssueState.ESCALATED.value, "history": history + [escalate_entry]})
            _create_notification(
                db, issue["asset_id"], issue_id, NotificationType.ESCALATION,
                f"Issue '{issue['type']}' escalated after {attempts} failed self-heal attempt(s).",
            )
            db.collection(COLLECTIONS.ASSETS).document(issue["asset_id"]).update({"status": AssetStatus.CRITICAL.value})
            return {"issue_id": issue_id, "resolved": False, "state": IssueState.ESCALATED.value}

        if history is not issue["history"]:
            doc.reference.update({"state": IssueState.OPEN.value, "history": history})
            return {"issue_id": issue_id, "resolved": False, "state": IssueState.OPEN.value}
        return {"issue_id": issue_id, "resolved": False, "state": issue["state"]}

    if issue["state"] == IssueState.OPEN.value:
        history_entry = {
            "state": IssueState.MONITORING.value,
            "timestamp": now,
            "note": "Metrics back in normal range; monitoring for sustained recovery.",
            "agent": "diagnostics",
        }
        doc.reference.update({"state": IssueState.MONITORING.value, "history": issue["history"] + [history_entry]})
        return {"issue_id": issue_id, "resolved": False, "state": IssueState.MONITORING.value}

    # already MONITORING and still normal - check whether the window has elapsed
    last_monitoring_ts = next(
        (h["timestamp"] for h in reversed(issue["history"]) if h["state"] == IssueState.MONITORING.value),
        now,
    )
    if isinstance(last_monitoring_ts, str):
        last_monitoring_ts = datetime.fromisoformat(last_monitoring_ts)
    elapsed = (now - last_monitoring_ts).total_seconds()

    if elapsed < MONITORING_WINDOW_SECONDS:
        return {"issue_id": issue_id, "resolved": False, "state": IssueState.MONITORING.value, "waiting_seconds": MONITORING_WINDOW_SECONDS - elapsed}

    history_entry = {
        "state": IssueState.RESOLVED.value,
        "timestamp": now,
        "note": f"Metrics stayed in normal range for the {MONITORING_WINDOW_SECONDS}s monitoring window; auto-resolved.",
        "agent": "diagnostics",
    }
    doc.reference.update(
        {"state": IssueState.RESOLVED.value, "resolved_at": now, "history": issue["history"] + [history_entry]}
    )
    _create_notification(db, issue["asset_id"], issue_id, NotificationType.RESOLVED, f"Issue '{issue['type']}' auto-resolved after sustained recovery.")
    _recompute_asset_health(db, issue["asset_id"])
    return {"issue_id": issue_id, "resolved": True, "state": IssueState.RESOLVED.value}


def _update_issue(issue_id: str, explanation: str, recommendation: str) -> dict:
    db = get_firestore_client()
    doc_ref = db.collection(COLLECTIONS.ISSUES).document(issue_id)
    if not doc_ref.get().exists:
        raise ValueError(f"unknown issue_id: {issue_id}")

    updates = {}
    if explanation:
        updates["explanation"] = explanation
    if recommendation:
        updates["recommendation"] = recommendation
    if updates:
        doc_ref.update(updates)
    return {"issue_id": issue_id, **updates}


def _create_notification(db, asset_id: str, issue_id: str, notif_type: NotificationType, message: str) -> None:
    notif_id = str(uuid.uuid4())
    db.collection(COLLECTIONS.NOTIFICATIONS).document(notif_id).set(
        {
            "asset_id": asset_id,
            "issue_id": issue_id,
            "message": message,
            "type": notif_type.value,
            "created_at": datetime.now(timezone.utc),
        }
    )


def _recompute_asset_health(db, asset_id: str) -> None:
    remaining = list(
        db.collection(COLLECTIONS.ISSUES)
        .where("asset_id", "==", asset_id)
        .where("state", "in", [IssueState.NEW.value, IssueState.OPEN.value, IssueState.MONITORING.value, IssueState.ESCALATED.value])
        .stream()
    )
    if not remaining:
        db.collection(COLLECTIONS.ASSETS).document(asset_id).update(
            {"status": AssetStatus.HEALTHY.value, "risk_score": RiskLevel.LOW.value, "risk_score_numeric": 0.0}
        )
