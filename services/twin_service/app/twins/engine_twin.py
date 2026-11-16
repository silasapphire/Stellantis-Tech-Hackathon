"""ICE digital twin built on OBD-II PIDs from the diesel OBD dataset.

Findings come from two places:
  * numeric thresholds on the PIDs (fault_library/ice_faults.json)
  * Diagnostic Trouble Codes the ECU has set (fault_library/dtc_catalog.json) - the
    dataset's own labels, so a vehicle with active DTCs is flagged from real evidence.
There is no wear/mileage signal in the data, so no time-to-failure is forecast for ICE;
risk is derived from finding severities and the number of active DTCs.
"""
from __future__ import annotations

import json
from copy import deepcopy
from datetime import timedelta
from functools import lru_cache
from pathlib import Path

from app.models import FailurePrediction, FaultFinding, TwinState
from app.twins.base import DigitalTwin
from common.schemas import RiskLevel, TelemetryReading

_ICE_FIELDS = (
    "load_pct", "coolant_temp", "map_kpa", "rpm", "speed_kph", "intake_air_temp", "maf",
    "fuel_rail_pressure_mpa", "baro_kpa", "control_module_voltage", "ambient_air_temp",
    "drive_mode", "dtc_count",
)
_CATALOG_PATH = Path(__file__).resolve().parent.parent / "fault_library" / "dtc_catalog.json"
_COOLANT_LIMIT_C = 105.0
_MIN_VOLTAGE = 12.6


@lru_cache(maxsize=1)
def dtc_catalog() -> dict:
    with open(_CATALOG_PATH, encoding="utf-8") as f:
        return json.load(f)


class EngineTwin(DigitalTwin):
    def get_state(self, readings: list[TelemetryReading]) -> TwinState:
        if not readings:
            raise ValueError(f"no telemetry available for asset {self.asset_id}")

        latest = readings[0]
        metrics = {field: getattr(latest, field) for field in _ICE_FIELDS}
        dtcs = list(latest.dtc_codes or [])

        derived: dict[str, float] = {"active_dtc_count": float(len(dtcs))}
        if metrics.get("coolant_temp") is not None:
            derived["coolant_margin_c"] = _COOLANT_LIMIT_C - metrics["coolant_temp"]
        if metrics.get("control_module_voltage") is not None:
            derived["voltage_margin_v"] = metrics["control_module_voltage"] - _MIN_VOLTAGE

        state = TwinState(
            asset_id=self.asset_id, vehicle_type="ICE", timestamp=latest.timestamp,
            metrics=metrics, derived=derived, active_dtcs=dtcs,
        )
        state.findings = self.check_thresholds(state) + _dtc_findings(dtcs)
        return state

    def predict_failure(self, state: TwinState, horizon_days: int) -> FailurePrediction:
        risk_level, risk_numeric = _risk_from(state)
        n = len(state.active_dtcs)
        if n:
            systems = sorted({dtc_catalog().get(c, {}).get("system", "unknown") for c in state.active_dtcs})
            explanation = (
                f"{n} active DTC(s) ({', '.join(state.active_dtcs)}) affecting the {', '.join(systems)} system(s). "
                "The OBD data has no wear or mileage trend, so no failure date is forecast; risk reflects fault severity."
            )
        elif state.findings:
            explanation = "Threshold findings are active but no DTCs are set; risk reflects finding severity."
        else:
            explanation = "No active DTCs and all monitored PIDs are within limits."
        return FailurePrediction(
            asset_id=self.asset_id, horizon_days=horizon_days, risk_score=risk_level,
            risk_score_numeric=risk_numeric, predicted_failure_horizon_days=None, explanation=explanation,
        )

    def simulate(self, state: TwinState, hypothetical_params: dict[str, float], horizon_days: int) -> TwinState:
        projected = deepcopy(state)
        projected.timestamp = state.timestamp + timedelta(days=horizon_days)
        for key, field in (("coolant_temp_delta", "coolant_temp"), ("voltage_delta", "control_module_voltage"),
                           ("intake_air_temp_delta", "intake_air_temp")):
            if key in hypothetical_params and projected.metrics.get(field) is not None:
                projected.metrics[field] += hypothetical_params[key]
        projected.findings = self.check_thresholds(projected) + _dtc_findings(projected.active_dtcs)
        return projected


def _dtc_findings(dtcs: list[str]) -> list[FaultFinding]:
    findings = []
    for code in dtcs:
        info = dtc_catalog().get(code, {"title": "Unknown code", "severity": "medium", "description": ""})
        findings.append(
            FaultFinding(
                fault_id=f"dtc_{code}", type=f"dtc_{code}", severity=info["severity"], field="dtc",
                value=1.0, threshold=0.0, operator=">", confidence=0.95,
                message=f"ECU has set {code}: {info['title']}. {info['description']}".strip(),
            )
        )
    return findings


def _risk_from(state: TwinState) -> tuple[RiskLevel, float]:
    severity_score = {"low": 10.0, "medium": 35.0, "high": 65.0}
    finding_score = max((severity_score[f.severity] for f in state.findings), default=0.0)
    numeric = min(finding_score + 5.0 * max(len(state.active_dtcs) - 1, 0), 100.0)
    if numeric >= 55:
        return RiskLevel.HIGH, numeric
    if numeric >= 25:
        return RiskLevel.MEDIUM, numeric
    return RiskLevel.LOW, numeric
