from __future__ import annotations

from copy import deepcopy
from datetime import timedelta

from app.models import FailurePrediction, TwinState
from app.twins.base import DigitalTwin
from common.schemas import RiskLevel, TelemetryReading

_EV_FIELDS = (
    "soc",
    "soh",
    "pack_voltage",
    "cell_temp_spread",
    "motor_temp",
    "inverter_temp",
    "coolant_temp",
    "charge_rate",
    "charge_cycles",
)

# Reference SOH degradation rate at 25°C ambient operating temperature. Heuristic,
# not electrochemistry: enough to produce a believable predictive-maintenance curve.
_BASE_DEGRADATION_PCT_PER_1000_CYCLES = 5.0
_REFERENCE_TEMP_C = 25.0
_SOH_FAILURE_THRESHOLD = 70.0
_DEFAULT_DAILY_CYCLE_RATE = 0.5


class EVTwin(DigitalTwin):
    def get_state(self, readings: list[TelemetryReading]) -> TwinState:
        if not readings:
            raise ValueError(f"no telemetry available for asset {self.asset_id}")

        latest = readings[0]
        metrics = {field: getattr(latest, field) for field in _EV_FIELDS}

        derived = {}
        window = readings[: min(len(readings), 50)]
        cycle_values = [r.charge_cycles for r in window if r.charge_cycles is not None]
        if len(cycle_values) >= 2 and len(window) >= 2:
            span_days = max((window[0].timestamp - window[-1].timestamp).total_seconds() / 86400, 0.1)
            derived["daily_cycle_rate"] = max((cycle_values[0] - cycle_values[-1]) / span_days, 0.0)
        else:
            derived["daily_cycle_rate"] = _DEFAULT_DAILY_CYCLE_RATE

        temps = [t for t in (metrics.get("motor_temp"), metrics.get("inverter_temp"), metrics.get("coolant_temp")) if t is not None]
        derived["avg_operating_temp"] = sum(temps) / len(temps) if temps else _REFERENCE_TEMP_C

        state = TwinState(
            asset_id=self.asset_id,
            vehicle_type="EV",
            timestamp=latest.timestamp,
            metrics=metrics,
            derived=derived,
        )
        state.findings = self.check_thresholds(state)
        return state

    def predict_failure(self, state: TwinState, horizon_days: int) -> FailurePrediction:
        current_soh = state.metrics.get("soh") or 100.0
        daily_cycle_rate = state.derived.get("daily_cycle_rate", _DEFAULT_DAILY_CYCLE_RATE)
        avg_temp = state.derived.get("avg_operating_temp", _REFERENCE_TEMP_C)

        degradation_per_1000_cycles = _degradation_rate(avg_temp)
        cycles_in_horizon = daily_cycle_rate * horizon_days
        soh_loss = degradation_per_1000_cycles / 1000.0 * cycles_in_horizon
        projected_soh = max(current_soh - soh_loss, 0.0)

        days_to_threshold = None
        per_day_loss = degradation_per_1000_cycles / 1000.0 * daily_cycle_rate
        if per_day_loss > 0 and current_soh > _SOH_FAILURE_THRESHOLD:
            days_to_threshold = (current_soh - _SOH_FAILURE_THRESHOLD) / per_day_loss

        risk_level, risk_numeric = _risk_from(state, projected_soh)

        explanation = (
            f"At the current usage rate (~{daily_cycle_rate:.2f} charge cycles/day, "
            f"avg operating temp {avg_temp:.1f}°C), projected SOH in {horizon_days} days "
            f"is {projected_soh:.1f}% (from {current_soh:.1f}% now)."
        )
        if days_to_threshold is not None:
            explanation += f" Estimated {days_to_threshold:.0f} days until SOH falls below the {_SOH_FAILURE_THRESHOLD:.0f}% service threshold."

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

        daily_cycle_rate = hypothetical_params.get("daily_cycle_rate", state.derived.get("daily_cycle_rate", _DEFAULT_DAILY_CYCLE_RATE))
        temp_delta = hypothetical_params.get("avg_temp_delta", 0.0)
        avg_temp = state.derived.get("avg_operating_temp", _REFERENCE_TEMP_C) + temp_delta

        degradation_per_1000_cycles = _degradation_rate(avg_temp)
        cycles_in_horizon = daily_cycle_rate * horizon_days
        soh_loss = degradation_per_1000_cycles / 1000.0 * cycles_in_horizon

        current_soh = state.metrics.get("soh") or 100.0
        projected.metrics["soh"] = max(current_soh - soh_loss, 0.0)
        projected.metrics["charge_cycles"] = (state.metrics.get("charge_cycles") or 0) + cycles_in_horizon
        for field in ("motor_temp", "inverter_temp", "coolant_temp"):
            if projected.metrics.get(field) is not None:
                projected.metrics[field] += temp_delta

        projected.derived["daily_cycle_rate"] = daily_cycle_rate
        projected.derived["avg_operating_temp"] = avg_temp
        projected.findings = self.check_thresholds(projected)
        return projected


def _degradation_rate(avg_temp: float) -> float:
    temp_factor = 1 + max(0.0, (avg_temp - _REFERENCE_TEMP_C) / _REFERENCE_TEMP_C) * 0.5
    return _BASE_DEGRADATION_PCT_PER_1000_CYCLES * temp_factor


def _risk_from(state: TwinState, projected_soh: float) -> tuple[RiskLevel, float]:
    severity_score = {"low": 10.0, "medium": 35.0, "high": 65.0}
    finding_score = max((severity_score[f.severity] for f in state.findings), default=0.0)
    soh_score = max(0.0, 100.0 - projected_soh) * 0.8
    numeric = min(finding_score + soh_score, 100.0)

    if numeric >= 55:
        return RiskLevel.HIGH, numeric
    if numeric >= 25:
        return RiskLevel.MEDIUM, numeric
    return RiskLevel.LOW, numeric
