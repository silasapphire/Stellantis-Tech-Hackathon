"""Shared pydantic schemas mirroring the Firestore data model.

Every service (twin_service, api, mcp_server, agents) imports these instead of
redefining the same document shapes, so a field added here is added everywhere.
"""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class VehicleType(StrEnum):
    EV = "EV"
    ICE = "ICE"


class AssetStatus(StrEnum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Asset(BaseModel):
    id: str
    name: str
    vehicle_type: VehicleType
    status: AssetStatus = AssetStatus.HEALTHY
    risk_score: RiskLevel = RiskLevel.LOW
    risk_score_numeric: float = 0.0
    created_at: datetime
    last_seen: datetime | None = None


class TelemetryReading(BaseModel):
    """Superset of EV + ICE fields; a given reading only fills in its vehicle type's fields."""

    asset_id: str
    timestamp: datetime

    # EV fields
    soc: float | None = None
    soh: float | None = None
    pack_voltage: float | None = None
    cell_temp_spread: float | None = None
    motor_temp: float | None = None
    inverter_temp: float | None = None
    charge_rate: float | None = None
    charge_cycles: int | None = None

    # ICE fields
    rpm: float | None = None
    oil_pressure: float | None = None
    oil_temp: float | None = None
    vibration_index: float | None = None
    fuel_rate: float | None = None
    air_fuel_ratio_proxy: float | None = None
    misfire_count: int | None = None

    # shared
    coolant_temp: float | None = None


class TwinSnapshot(BaseModel):
    asset_id: str
    timestamp: datetime
    modeled_state: dict[str, Any]
    predicted_failure_horizon_days: float | None = None


class IssueState(StrEnum):
    NEW = "NEW"
    OPEN = "OPEN"
    MONITORING = "MONITORING"
    RESOLVED = "RESOLVED"
    ESCALATED = "ESCALATED"


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class IssueHistoryEntry(BaseModel):
    state: IssueState
    timestamp: datetime
    note: str
    agent: str


class Issue(BaseModel):
    id: str
    asset_id: str
    type: str
    state: IssueState = IssueState.NEW
    severity: Severity
    confidence: float = 1.0
    detected_at: datetime
    resolved_at: datetime | None = None
    explanation: str = ""
    recommendation: str = ""
    self_heal_action: str | None = None
    self_heal_attempts: int = 0
    history: list[IssueHistoryEntry] = Field(default_factory=list)


class NotificationType(StrEnum):
    ALERT = "alert"
    RESOLVED = "resolved"
    SELF_HEAL = "self_heal"
    ESCALATION = "escalation"
    PREDICTION = "prediction"


class Notification(BaseModel):
    id: str
    asset_id: str
    issue_id: str
    message: str
    type: NotificationType
    created_at: datetime


class ChatMessage(BaseModel):
    id: str
    role: Literal["user", "assistant", "tool"]
    content: str
    tool_calls: list[dict[str, Any]] | None = None
    timestamp: datetime


class SustainabilityPeriod(BaseModel):
    asset_id: str
    period_start: datetime
    period_end: datetime
    energy_or_fuel_used: float
    estimated_co2: float
    baseline_co2: float
