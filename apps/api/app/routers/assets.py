from __future__ import annotations

from datetime import datetime, timezone

from common.firestore_client import COLLECTIONS, get_firestore_client
from common.schemas import AssetStatus, RiskLevel, VehicleType
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(tags=["assets"])


class RegisterAssetRequest(BaseModel):
    asset_id: str
    name: str
    vehicle_type: VehicleType


@router.get("/assets")
def list_assets() -> list[dict]:
    db = get_firestore_client()
    return [{"id": doc.id, **doc.to_dict()} for doc in db.collection(COLLECTIONS.ASSETS).stream()]


@router.get("/assets/{asset_id}")
def get_asset(asset_id: str) -> dict:
    db = get_firestore_client()
    doc = db.collection(COLLECTIONS.ASSETS).document(asset_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail=f"unknown asset_id: {asset_id}")
    return {"id": doc.id, **doc.to_dict()}


@router.post("/assets", status_code=201)
def register_asset(body: RegisterAssetRequest) -> dict:
    db = get_firestore_client()
    now = datetime.now(timezone.utc)
    db.collection(COLLECTIONS.ASSETS).document(body.asset_id).set(
        {
            "name": body.name,
            "vehicle_type": body.vehicle_type.value,
            "status": AssetStatus.HEALTHY.value,
            "risk_score": RiskLevel.LOW.value,
            "risk_score_numeric": 0.0,
            "created_at": now,
            "last_seen": None,
        }
    )
    return {"status": "registered", "asset_id": body.asset_id}
