"""Plain (non-tool) Firestore read helpers shared across tool modules.

Kept separate from the `@mcp.tool()` functions so telemetry.py and twin.py can
both fetch the same underlying data without one importing the other's tools.
"""
from __future__ import annotations

from common.firestore_client import COLLECTIONS, get_firestore_client


def get_asset(asset_id: str) -> dict:
    db = get_firestore_client()
    doc = db.collection(COLLECTIONS.ASSETS).document(asset_id).get()
    if not doc.exists:
        raise ValueError(f"unknown asset_id: {asset_id}")
    return {"id": doc.id, **doc.to_dict()}


def get_recent_readings(asset_id: str, limit: int = 100) -> list[dict]:
    db = get_firestore_client()
    query = (
        db.collection(COLLECTIONS.TELEMETRY)
        .document(asset_id)
        .collection("readings")
        .order_by("timestamp", direction="DESCENDING")
        .limit(limit)
    )
    return [doc.to_dict() for doc in query.stream()]
