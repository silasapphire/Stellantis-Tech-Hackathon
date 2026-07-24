from __future__ import annotations

from copy import deepcopy
from datetime import timedelta

from app.models import FailurePrediction, TwinState
from app.twins.base import DigitalTwin
from common.schemas import RiskLevel, TelemetryReading

_ICE_FIELDS = (
    "rpm",
    "oil_pressure",
    "oil_temp",
    "coolant_temp",
    "vibration_index",
    "fuel_rate",
    "air_fuel_ratio_proxy",
    "misfire_count",
)

# Heuristic mechanical-wear proxy model, not a physical wear simulation: enough to
# produce a believable predictive-maintenance curve from vibration/misfire/oil signals.
_BASE_WEAR_RATE_PCT_PER_DAY = 0.5
_BASELINE_VIBRATION = 3.0
_BASELINE_OIL_TEMP = 100.0
_WEAR_CRITICAL_THRESHOLD = 80.0


class EngineTwin(DigitalTwin):
    def get_state(self, readings: list[TelemetryReading]) -> TwinState:
        if not readings:
            raise ValueError(f"no telemetry available for asset {self.asset_id}")

        latest = readings[0]
        metrics = {field: getattr(latest, field) for field in _ICE_FIELDS}

        derived = {"wear_score": _wear_score(metrics)}

        state = TwinState(
            asset_id=self.asset_id,
            vehicle_type="ICE",
            timestamp=latest.timestamp,
            metrics=metrics,
            derived=derived,
        )
        state.findings = self.check_thresholds(state)
        return state

    def predict_failure(self, state: TwinState, horizon_days: int) -> FailurePrediction:
        current_wear = state.derived.get("wear_score", 0.0)
        vibration = state.metrics.get("vibration_index") or _BASELINE_VIBRATION
        oil_temp = state.metrics.get("oil_temp") or _BASELINE_OIL_TEMP

        wear_rate_per_day = _wear_rate(vibration, oil_temp)
        projected_wear = min(current_wear + wear_rate_per_day * horizon_days, 100.0)

        days_to_threshold = None
        if wear_rate_per_day > 0 and current_wear < _WEAR_CRITICAL_THRESHOLD:
            days_to_threshold = (_WEAR_CRITICAL_THRESHOLD - current_wear) / wear_rate_per_day

        risk_level, risk_numeric = _risk_from(state, projected_wear)

        explanation = (
            f"Current mechanical-wear proxy score is {current_wear:.0f}/100 "
            f"(vibration {vibration:.1f}, oil temp {oil_temp:.0f}°C). Projected in "
            f"{horizon_days} days: {projected_wear:.0f}/100."
        )
        if days_to_threshold is not None:
            explanation += f" Estimated {days_to_threshold:.0f} days until wear crosses the {_WEAR_CRITICAL_THRESHOLD:.0f}/100 service threshold."

        return FailurePrediction(
            asset_id=self.asset_id,
            horizon_days=horizon_days,
            risk_score=risk_level,
            risk_score_numeric=risk_numeric,
            predicted_failure_horizon_days=days_to_threshold,
            explanation=explanation,
        )

    def simulate(
        self, state: TwinState, hypothetical_params: dict[str, float], horizon_days: int
    ) -> TwinState:
        projected = deepcopy(state)
        projected.timestamp = state.timestamp + timedelta(days=horizon_days)

        vibration_delta = hypothetical_params.get("vibration_delta", 0.0)
        oil_temp_delta = hypothetical_params.get("oil_temp_delta", 0.0)
        misfire_rate_per_day = hypothetical_params.get("misfire_rate_per_day", 0.0)

        if projected.metrics.get("vibration_index") is not None:
            projected.metrics["vibration_index"] += vibration_delta
        if projected.metrics.get("oil_temp") is not None:
            projected.metrics["oil_temp"] += oil_temp_delta
        if projected.metrics.get("coolant_temp") is not None:
            projected.metrics["coolant_temp"] += oil_temp_delta * 0.5
        projected.metrics["misfire_count"] = (state.metrics.get("misfire_count") or 0) + misfire_rate_per_day * horizon_days

        projected.derived["wear_score"] = min(_wear_score(projected.metrics), 100.0)
        projected.findings = self.check_thresholds(projected)
        return projected


def _wear_score(metrics: dict) -> float:
    vibration = metrics.get("vibration_index") or 0.0
    misfires = metrics.get("misfire_count") or 0
    oil_pressure = metrics.get("oil_pressure")
    low_pressure_penalty = max(0.0, 20.0 - oil_pressure) * 2 if oil_pressure is not None else 0.0
    score = vibration * 5 + misfires * 3 + low_pressure_penalty
    return max(0.0, min(score, 100.0))


def _wear_rate(vibration: float, oil_temp: float) -> float:
    vibration_factor = 1 + max(0.0, (vibration - _BASELINE_VIBRATION) / _BASELINE_VIBRATION) * 0.5
    oil_temp_factor = 1 + max(0.0, (oil_temp - _BASELINE_OIL_TEMP) / _BASELINE_OIL_TEMP) * 0.5
    return _BASE_WEAR_RATE_PCT_PER_DAY * vibration_factor * oil_temp_factor


def _risk_from(state: TwinState, projected_wear: float) -> tuple[RiskLevel, float]:
    severity_score = {"low": 10.0, "medium": 35.0, "high": 65.0}
    finding_score = max((severity_score[f.severity] for f in state.findings), default=0.0)
    wear_component = projected_wear * 0.8
    numeric = min(finding_score + wear_component, 100.0)

    if numeric >= 55:
        return RiskLevel.HIGH, numeric
    if numeric >= 25:
        return RiskLevel.MEDIUM, numeric
    return RiskLevel.LOW, numeric
