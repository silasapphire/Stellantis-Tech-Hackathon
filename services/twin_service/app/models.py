from __future__ import annotations

from datetime import datetime
from typing import Any

from common.schemas import RiskLevel, Severity, VehicleType
from pydantic import BaseModel, Field


class FaultRule(BaseModel):
    id: str
    field: str
    operator: str  # ">" or "<"
    threshold: float
    severity: Severity
    type: str
    message: str


class FaultFinding(BaseModel):
    fault_id: str
    type: str
    severity: Severity
    field: str
    value: float
    threshold: float
    operator: str
    message: str


class TwinState(BaseModel):
    asset_id: str
    vehicle_type: VehicleType
    timestamp: datetime
    metrics: dict[str, float | int | None] = Field(default_factory=dict)
    derived: dict[str, float] = Field(default_factory=dict)
    findings: list[FaultFinding] = Field(default_factory=list)


class FailurePrediction(BaseModel):
    asset_id: str
    horizon_days: int
    risk_score: RiskLevel
    risk_score_numeric: float
    predicted_failure_horizon_days: float | None
    explanation: str


class TwinStateRequest(BaseModel):
    readings: list[dict[str, Any]]


class SimulateRequest(BaseModel):
    readings: list[dict[str, Any]]
    hypothetical_params: dict[str, float] = Field(default_factory=dict)
    horizon_days: int = 30


class PredictRequest(BaseModel):
    readings: list[dict[str, Any]]
    horizon_days: int = 30
