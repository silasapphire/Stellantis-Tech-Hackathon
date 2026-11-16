"""Plain (non-tool) document-store read helpers shared across tool modules.

Kept separate from the `@mcp.tool()` functions so telemetry.py and twin.py can
both fetch the same underlying data without one importing the other's tools.
"""
from __future__ import annotations

from common.store import COLLECTIONS, get_store


def get_asset(asset_id: str) -> dict:
    db = get_store()
    doc = db.collection(COLLECTIONS.ASSETS).document(asset_id).get()
    if not doc.exists:
        raise ValueError(f"unknown asset_id: {asset_id}")
    return {"id": doc.id, **doc.to_dict()}


def get_recent_readings(asset_id: str, limit: int = 100) -> list[dict]:
    db = get_store()
    query = (
        db.collection(COLLECTIONS.TELEMETRY)
        .document(asset_id)
        .collection("readings")
        .order_by("timestamp", direction="DESCENDING")
        .limit(limit)
    )
    return [doc.to_dict() for doc in query.stream()]
