from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query

from app.models import FailurePrediction, PredictRequest, SimulateRequest, TwinState, TwinStateRequest
from app.twins.factory import detect_vehicle_type, get_twin
from common.schemas import TelemetryReading, VehicleType

app = FastAPI(title="Digital Twin Service")


def _parse_readings(raw: list[dict]) -> list[TelemetryReading]:
    readings = [TelemetryReading(**r) for r in raw]
    # newest first, so twin logic can assume readings[0] is the latest
    return sorted(readings, key=lambda r: r.timestamp, reverse=True)


def _resolve_vehicle_type(vehicle_type: str | None, raw_readings: list[dict]) -> VehicleType:
    if vehicle_type:
        return VehicleType(vehicle_type)
    if raw_readings:
        detected = detect_vehicle_type(raw_readings[0])
        if detected:
            return detected
    raise HTTPException(status_code=422, detail="vehicle_type not provided and could not be auto-detected from readings")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/twin/{asset_id}/state", response_model=TwinState)
def get_state(asset_id: str, body: TwinStateRequest, vehicle_type: str | None = Query(default=None)) -> TwinState:
    vt = _resolve_vehicle_type(vehicle_type, body.readings)
    readings = _parse_readings(body.readings)
    twin = get_twin(vt, asset_id)
    return twin.get_state(readings)


@app.post("/twin/{asset_id}/predict", response_model=FailurePrediction)
def predict_failure(asset_id: str, body: PredictRequest, vehicle_type: str | None = Query(default=None)) -> FailurePrediction:
    vt = _resolve_vehicle_type(vehicle_type, body.readings)
    readings = _parse_readings(body.readings)
    twin = get_twin(vt, asset_id)
    state = twin.get_state(readings)
    return twin.predict_failure(state, body.horizon_days)


@app.post("/twin/{asset_id}/simulate", response_model=TwinState)
def simulate(asset_id: str, body: SimulateRequest, vehicle_type: str | None = Query(default=None)) -> TwinState:
    vt = _resolve_vehicle_type(vehicle_type, body.readings)
    readings = _parse_readings(body.readings)
    twin = get_twin(vt, asset_id)
    state = twin.get_state(readings)
    return twin.simulate(state, body.hypothetical_params, body.horizon_days)
