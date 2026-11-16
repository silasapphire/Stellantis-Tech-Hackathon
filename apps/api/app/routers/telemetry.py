from __future__ import annotations

from datetime import datetime, timezone

from common.store import COLLECTIONS, TELEMETRY_RETENTION, get_store
from common.schemas import AssetStatus, RiskLevel, TelemetryReading
from common.vehicle_detection import detect_vehicle_type
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(tags=["telemetry"])

_ingest_counts: dict[str, int] = {}


@router.post("/telemetry", status_code=201)
def ingest_telemetry(reading: TelemetryReading) -> dict:
    db = get_store()
    now = datetime.now(timezone.utc)

    asset_ref = db.collection(COLLECTIONS.ASSETS).document(reading.asset_id)
    asset_doc = asset_ref.get()

    if not asset_doc.exists:
        vehicle_type = detect_vehicle_type(reading.model_dump())
        if vehicle_type is None:
            raise HTTPException(
                status_code=422,
                detail="cannot auto-detect vehicle_type from this reading; register the asset explicitly via POST /assets first",
            )
        asset_ref.set(
            {
                "name": reading.asset_id,
                "vehicle_type": vehicle_type.value,
                "status": AssetStatus.HEALTHY.value,
                "risk_score": RiskLevel.LOW.value,
                "risk_score_numeric": 0.0,
                "created_at": now,
                "last_seen": now,
            }
        )
    else:
        asset_ref.update({"last_seen": now})

    readings = db.collection(COLLECTIONS.TELEMETRY).document(reading.asset_id).collection("readings")
    readings.add(reading.model_dump(mode="json"))
    _ingest_counts[reading.asset_id] = _ingest_counts.get(reading.asset_id, 0) + 1
    if _ingest_counts[reading.asset_id] % 200 == 0:  # cap growth: replay never stops
        db.prune_collection(f"{COLLECTIONS.TELEMETRY}/{reading.asset_id}/readings", "timestamp", TELEMETRY_RETENTION)
    return {"status": "ingested", "asset_id": reading.asset_id}


@router.get("/telemetry/{asset_id}/latest")
def get_latest_telemetry(asset_id: str) -> dict:
    db = get_store()
    query = (
        db.collection(COLLECTIONS.TELEMETRY)
        .document(asset_id)
        .collection("readings")
        .order_by("timestamp", direction="DESCENDING")
        .limit(1)
    )
    docs = list(query.stream())
    if not docs:
        raise HTTPException(status_code=404, detail=f"no telemetry for asset_id: {asset_id}")
    return docs[0].to_dict()


@router.get("/telemetry/{asset_id}/history")
def get_telemetry_history(asset_id: str, limit: int = Query(default=100, le=1000)) -> list[dict]:
    db = get_store()
    query = (
        db.collection(COLLECTIONS.TELEMETRY)
        .document(asset_id)
        .collection("readings")
        .order_by("timestamp", direction="DESCENDING")
        .limit(limit)
    )
    return [doc.to_dict() for doc in query.stream()]
