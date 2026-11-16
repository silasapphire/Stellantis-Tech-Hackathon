from __future__ import annotations

import os
from datetime import datetime, timezone

import httpx
from common.schemas import AssetStatus, RiskLevel, VehicleType
from common.store import COLLECTIONS, get_store
from fastapi import APIRouter, HTTPException
from mcp_server.tools._twin_client import call_twin_service
from pydantic import BaseModel

router = APIRouter(tags=["assets"])

# One shared client: creating a client per call costs seconds on Windows (SSL context + proxy lookup).
_http = httpx.Client(timeout=5.0, trust_env=False)

SIMULATOR_URL = os.environ.get("SIMULATOR_URL", "http://127.0.0.1:8200")


class RegisterAssetRequest(BaseModel):
    asset_id: str
    name: str
    vehicle_type: VehicleType


class InjectFaultRequest(BaseModel):
    fault_type: str
    target_value: float | None = None
    ramp_seconds: float | None = None


class AutopilotRequest(BaseModel):
    enabled: bool
    interval_seconds: float = 90
    hold_seconds: float = 120


@router.get("/assets")
def list_assets(with_latest: bool = False) -> list[dict]:
    """All assets; `with_latest=true` also attaches each asset's newest telemetry reading."""
    db = get_store()
    assets = [{"id": doc.id, **doc.to_dict()} for doc in db.collection(COLLECTIONS.ASSETS).stream()]
    if with_latest:
        for a in assets:
            latest = (
                db.collection(COLLECTIONS.TELEMETRY).document(a["id"]).collection("readings")
                .order_by("timestamp", direction="DESCENDING").limit(1).stream()
            )
            a["latest"] = next((d.to_dict() for d in latest), None)
    return assets


@router.get("/assets/{asset_id}")
def get_asset(asset_id: str) -> dict:
    db = get_store()
    doc = db.collection(COLLECTIONS.ASSETS).document(asset_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail=f"unknown asset_id: {asset_id}")
    return {"id": doc.id, **doc.to_dict()}


@router.post("/assets", status_code=201)
def register_asset(body: RegisterAssetRequest) -> dict:
    """Idempotent: re-registering an existing asset only refreshes its name/type."""
    db = get_store()
    ref = db.collection(COLLECTIONS.ASSETS).document(body.asset_id)
    if ref.get().exists:
        ref.update({"name": body.name, "vehicle_type": body.vehicle_type.value})
        return {"status": "updated", "asset_id": body.asset_id}
    ref.set(
        {
            "name": body.name,
            "vehicle_type": body.vehicle_type.value,
            "status": AssetStatus.HEALTHY.value,
            "risk_score": RiskLevel.LOW.value,
            "risk_score_numeric": 0.0,
            "created_at": datetime.now(timezone.utc),
            "last_seen": None,
        }
    )
    return {"status": "registered", "asset_id": body.asset_id}


@router.get("/assets/{asset_id}/twin")
def get_twin(asset_id: str) -> dict:
    """Current digital-twin state and failure prediction (read-only: does not persist the prediction)."""
    try:
        return {
            "state": call_twin_service(asset_id, "state"),
            "prediction": call_twin_service(asset_id, "predict", {"horizon_days": 30}),
        }
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"twin service unavailable: {exc}") from exc


@router.post("/assets/{asset_id}/inject-fault")
def inject_fault(asset_id: str, body: InjectFaultRequest) -> dict:
    """Demo helper: overlay a fault on the replayed data so the diagnose -> self-heal loop can be shown."""
    try:
        response = _http.post(f"{SIMULATOR_URL}/simulator/fault/{asset_id}", json=body.model_dump(exclude_none=True), timeout=5.0)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"simulator unavailable: {exc}") from exc
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.json().get("detail", "simulator error"))
    return response.json()


@router.delete("/assets/{asset_id}/fault")
def clear_fault(asset_id: str) -> dict:
    """Demo helper: remove an injected fault (the overlay ramps back to the real values)."""
    try:
        return _http.delete(f"{SIMULATOR_URL}/simulator/fault/{asset_id}", timeout=5.0).json()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"simulator unavailable: {exc}") from exc


@router.get("/simulator/status")
def simulator_status() -> dict:
    try:
        return _http.get(f"{SIMULATOR_URL}/simulator/status", timeout=5.0).json()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"simulator unavailable: {exc}") from exc


@router.post("/simulator/autopilot")
def simulator_autopilot(body: AutopilotRequest) -> dict:
    try:
        return _http.post(f"{SIMULATOR_URL}/simulator/autopilot", json=body.model_dump(), timeout=5.0).json()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"simulator unavailable: {exc}") from exc
