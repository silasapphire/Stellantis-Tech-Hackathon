"""Shared pydantic schemas mirroring the document-store data model (see common.store).

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
    """Superset of EV + ICE fields; a given reading only fills in its vehicle type's fields.

    EV fields come from the NASA Li-ion aging dataset (a single cell under test, so voltage is
    per-cell). ICE fields are the OBD-II PIDs from the diesel OBD dataset, in SI units.
    """

    asset_id: str
    timestamp: datetime

    # EV (battery) fields
    soc: float | None = None  # state of charge, % (coulomb counted)
    soh: float | None = None  # state of health, % = measured capacity / 2.0 Ah rated
    capacity_ah: float | None = None
    cell_voltage: float | None = None  # V
    current: float | None = None  # A (negative = discharging in the source data)
    battery_temp: float | None = None  # degC
    ambient_temp: float | None = None  # degC
    charge_cycles: int | None = None  # completed discharge cycles
    phase: str | None = None  # "charge" | "discharge"

    # ICE (OBD-II) fields
    load_pct: float | None = None  # calculated engine load, %
    coolant_temp: float | None = None  # ECT, degC
    map_kpa: float | None = None  # intake manifold absolute pressure
    rpm: float | None = None
    speed_kph: float | None = None  # VSS
    intake_air_temp: float | None = None  # IAT, degC
    maf: float | None = None  # mass air flow, source units (undocumented in the dataset)
    fuel_rail_pressure_mpa: float | None = None  # FRP
    baro_kpa: float | None = None
    control_module_voltage: float | None = None  # VPWR, V
    ambient_air_temp: float | None = None  # AAT, degC
    drive_mode: int | None = None  # dataset "Mode": 0 idle, 1 low speed, 2 high speed
    dtc_codes: list[str] | None = None  # active Diagnostic Trouble Codes
    dtc_count: int | None = None


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
