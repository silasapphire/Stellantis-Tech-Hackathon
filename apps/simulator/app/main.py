from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.state import SimulatedAsset

load_dotenv()

logger = logging.getLogger("simulator")
logging.basicConfig(level=logging.INFO)

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")
TICK_SECONDS = float(os.environ.get("SIMULATOR_TICK_SECONDS", "3"))

assets: dict[str, SimulatedAsset] = {
    "ev-1": SimulatedAsset("ev-1", "Fleet EV Sedan", "EV"),
    "ice-1": SimulatedAsset("ice-1", "Fleet Delivery Van", "ICE"),
}


async def _tick_loop() -> None:
    async with httpx.AsyncClient(timeout=5.0) as client:
        while True:
            for asset in assets.values():
                payload = asset.tick()
                try:
                    await client.post(f"{API_BASE_URL}/telemetry", json=payload)
                except httpx.HTTPError as exc:
                    logger.warning("failed to post telemetry for %s: %s", asset.asset_id, exc)
            await asyncio.sleep(TICK_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_tick_loop())
    try:
        yield
    finally:
        task.cancel()


app = FastAPI(title="Telemetry Simulator", lifespan=lifespan)


class RegisterAssetRequest(BaseModel):
    asset_id: str
    name: str
    vehicle_type: str


class InjectFaultRequest(BaseModel):
    fault_type: str


@app.get("/simulator/assets")
def list_assets() -> list[dict]:
    return [
        {
            "asset_id": a.asset_id,
            "name": a.name,
            "vehicle_type": a.vehicle_type,
            "metrics": a.metrics,
            "fault": a.fault_status,
        }
        for a in assets.values()
    ]


@app.post("/simulator/assets", status_code=201)
def register_asset(body: RegisterAssetRequest) -> dict:
    if body.vehicle_type not in ("EV", "ICE"):
        raise HTTPException(status_code=422, detail="vehicle_type must be EV or ICE")
    assets[body.asset_id] = SimulatedAsset(body.asset_id, body.name, body.vehicle_type)
    return {"status": "registered", "asset_id": body.asset_id}


@app.post("/simulator/fault/{asset_id}")
def inject_fault(asset_id: str, body: InjectFaultRequest) -> dict:
    asset = _get_asset(asset_id)
    try:
        asset.inject_fault(body.fault_type)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "fault_injected", "asset_id": asset_id, "fault_type": body.fault_type}


@app.delete("/simulator/fault/{asset_id}")
def clear_fault(asset_id: str) -> dict:
    asset = _get_asset(asset_id)
    asset.clear_fault()
    return {"status": "fault_clearing", "asset_id": asset_id}


def _get_asset(asset_id: str) -> SimulatedAsset:
    asset = assets.get(asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail=f"unknown asset_id: {asset_id}")
    return asset
