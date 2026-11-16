from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

load_dotenv()

from app.replay import DatasetReplayer  # noqa: E402
from app.state import ReplayAsset  # noqa: E402

logger = logging.getLogger("simulator")
logging.basicConfig(level=logging.INFO)

API_BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000")
TICK_SECONDS = float(os.environ.get("SIMULATOR_TICK_SECONDS", "3"))
EV_ROWS_PER_TICK = int(os.environ.get("EV_ROWS_PER_TICK", "3"))
ICE_ROWS_PER_TICK = int(os.environ.get("ICE_ROWS_PER_TICK", "1"))
_FLEET_FILE = Path(__file__).resolve().parent.parent / "data" / "fleet.json"


def _load_fleet() -> dict[str, ReplayAsset]:
    fleet: dict[str, ReplayAsset] = {}
    for spec in json.loads(_FLEET_FILE.read_text(encoding="utf-8")):
        if spec["vehicle_type"] == "EV":
            replayer = DatasetReplayer.for_ev(spec["source"], spec.get("start_fraction", 0.0), EV_ROWS_PER_TICK)
        else:
            replayer = DatasetReplayer.for_ice(spec["source"], spec.get("start_fraction", 0.0), ICE_ROWS_PER_TICK)
        fleet[spec["asset_id"]] = ReplayAsset(spec["asset_id"], spec["name"], spec["vehicle_type"], replayer)
        logger.info("replaying %s (%d rows) for %s", spec["source"], len(replayer.rows), spec["asset_id"])
    return fleet


assets: dict[str, ReplayAsset] = _load_fleet()


async def _register_assets(client: httpx.AsyncClient) -> None:
    for asset in assets.values():
        body = {"asset_id": asset.asset_id, "name": asset.name, "vehicle_type": asset.vehicle_type}
        for _ in range(30):  # the API may still be starting
            try:
                await client.post(f"{API_BASE_URL}/assets", json=body)
                break
            except httpx.HTTPError:
                await asyncio.sleep(2)


async def _tick_loop() -> None:
    async with httpx.AsyncClient(timeout=5.0) as client:
        await _register_assets(client)
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
    tasks = [asyncio.create_task(_tick_loop()), asyncio.create_task(_autopilot_loop())]
    try:
        yield
    finally:
        for t in tasks:
            t.cancel()


app = FastAPI(title="Dataset Replay Simulator", lifespan=lifespan)


class InjectFaultRequest(BaseModel):
    fault_type: str
    target_value: float | None = None  # severity: where the field ramps to (defaults to the preset's)
    ramp_seconds: float | None = None  # how fast it ramps in (defaults to the preset's)


class AutopilotRequest(BaseModel):
    enabled: bool
    interval_seconds: float = 90  # gap between automatic faults
    hold_seconds: float = 120  # how long an automatic fault stays before it is cleared


# Autopilot: injects a random fault on a random asset every `interval`, clears it after `hold`
# unless a self-heal got there first. Entirely optional; off at startup.
autopilot = {"enabled": False, "interval_seconds": 90.0, "hold_seconds": 120.0, "last_event": None}
_autopilot_injected: dict[str, float] = {}
_last_autopilot_inject = 0.0


async def _autopilot_loop() -> None:
    import random
    import time

    global _last_autopilot_inject
    while True:
        await asyncio.sleep(2)
        now = time.monotonic()
        for asset_id, t in list(_autopilot_injected.items()):
            asset = assets.get(asset_id)
            if asset is None or asset.active_fault is None:
                _autopilot_injected.pop(asset_id, None)  # healed or gone
            elif now - t >= autopilot["hold_seconds"] and not asset.active_fault.clearing:
                asset.clear_fault()
                autopilot["last_event"] = f"cleared {asset.active_fault.fault_type} on {asset_id}"
                _autopilot_injected.pop(asset_id, None)
        if not autopilot["enabled"] or now - _last_autopilot_inject < autopilot["interval_seconds"]:
            continue
        if any(a.active_fault for a in assets.values()):
            continue  # one fault at a time keeps the demo readable
        from app.fault_injection import FAULT_PRESETS

        asset = random.choice(list(assets.values()))
        fault = random.choice([k for k, p in FAULT_PRESETS.items() if p.vehicle_type == asset.vehicle_type])
        asset.inject_fault(fault)
        _autopilot_injected[asset.asset_id] = now
        _last_autopilot_inject = now
        autopilot["last_event"] = f"injected {fault} on {asset.asset_id}"


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "assets": len(assets)}


@app.get("/simulator/assets")
def list_assets() -> list[dict]:
    return [
        {"asset_id": a.asset_id, "name": a.name, "vehicle_type": a.vehicle_type,
         "replay_position": round(a.replayer.position, 4), "fault": a.fault_status}
        for a in assets.values()
    ]


@app.get("/simulator/status")
def status() -> dict:
    from app.fault_injection import FAULT_PRESETS

    return {
        "tick_seconds": TICK_SECONDS,
        "assets": {a.asset_id: a.fault_status for a in assets.values()},
        "presets": {
            k: {"field": p.field, "target_value": p.target_value, "vehicle_type": p.vehicle_type, "label": p.label,
                "unit": p.unit, "lo": p.lo, "hi": p.hi, "hint": p.hint, "ramp_seconds": p.ramp_ticks * TICK_SECONDS}
            for k, p in FAULT_PRESETS.items()
        },
        "autopilot": autopilot,
    }


@app.post("/simulator/autopilot")
def set_autopilot(body: AutopilotRequest) -> dict:
    autopilot.update(enabled=body.enabled, interval_seconds=max(10.0, body.interval_seconds),
                     hold_seconds=max(10.0, body.hold_seconds))
    if body.enabled:
        autopilot["last_event"] = "autopilot on"
    return autopilot


@app.post("/simulator/fault/{asset_id}")
def inject_fault(asset_id: str, body: InjectFaultRequest) -> dict:
    asset = _get_asset(asset_id)
    ramp_ticks = round(body.ramp_seconds / TICK_SECONDS) if body.ramp_seconds else None
    try:
        asset.inject_fault(body.fault_type, body.target_value, ramp_ticks)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "fault_injected", "asset_id": asset_id, "fault_type": body.fault_type}


@app.delete("/simulator/fault/{asset_id}")
def clear_fault(asset_id: str) -> dict:
    asset = _get_asset(asset_id)
    cleared = asset.clear_fault()
    return {"status": "fault_clearing" if cleared else "no_injected_fault", "cleared": cleared, "asset_id": asset_id}


def _get_asset(asset_id: str) -> ReplayAsset:
    asset = assets.get(asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail=f"unknown asset_id: {asset_id}")
    return asset
