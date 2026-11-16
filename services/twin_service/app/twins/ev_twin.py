"""EV digital twin of the battery, built on the NASA Li-ion aging data.

The twin tracks state of charge/health and projects capacity fade using a model
fitted during data preparation (data/processed/ev_degradation.json: median SOH loss
per discharge cycle, grouped by ambient temperature). It is a statistical fade
model, not electrochemistry.
"""
from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import timedelta
from functools import lru_cache
from pathlib import Path

from app.models import FailurePrediction, TwinState
from app.twins.base import DigitalTwin
from common.schemas import RiskLevel, TelemetryReading

_EV_FIELDS = (
    "soc", "soh", "capacity_ah", "cell_voltage", "current", "battery_temp",
    "ambient_temp", "charge_cycles",
)
_REPO_ROOT = Path(__file__).resolve().parents[4]
_DEGRADATION_PATH = Path(os.environ.get("EV_DEGRADATION_JSON", _REPO_ROOT / "data" / "processed" / "ev_degradation.json"))

_SOH_FAILURE_THRESHOLD = 70.0  # EOL per the dataset README: 30% fade from 2.0 Ah
_DEFAULT_DAILY_CYCLE_RATE = 1.0  # assumption: one full discharge cycle per day of fleet use
_FALLBACK_FADE_PCT_PER_CYCLE = 0.2


@lru_cache(maxsize=1)
def _degradation_model() -> dict:
    try:
        return json.loads(_DEGRADATION_PATH.read_text())
    except (OSError, ValueError):
        return {"per_ambient_temp": {}, "default_fade_pct_per_cycle": _FALLBACK_FADE_PCT_PER_CYCLE}


def fade_per_cycle(ambient_temp: float | None, extra_temp: float = 0.0) -> float:
    """Median SOH loss (%/cycle) for the dataset group whose ambient temperature is closest."""
    model = _degradation_model()
    groups = model.get("per_ambient_temp", {})
    default = model.get("default_fade_pct_per_cycle", _FALLBACK_FADE_PCT_PER_CYCLE)
    if ambient_temp is None or not groups:
        return default
    target = ambient_temp + extra_temp
    nearest = min(groups, key=lambda k: abs(float(k) - target))
    return float(groups[nearest]["fade_pct_per_cycle"])


class EVTwin(DigitalTwin):
    def get_state(self, readings: list[TelemetryReading]) -> TwinState:
        if not readings:
            raise ValueError(f"no telemetry available for asset {self.asset_id}")

        latest = readings[0]
        metrics = {field: getattr(latest, field) for field in _EV_FIELDS}
        if latest.phase:
            metrics["phase_is_charging"] = 1.0 if latest.phase == "charge" else 0.0

        soh = metrics.get("soh")
        fade = fade_per_cycle(latest.ambient_temp)
        derived = {"fade_pct_per_cycle": fade, "daily_cycle_rate": _DEFAULT_DAILY_CYCLE_RATE}
        if soh is not None:
            derived["soh_margin_pct"] = soh - _SOH_FAILURE_THRESHOLD
            derived["remaining_cycles"] = max((soh - _SOH_FAILURE_THRESHOLD) / fade, 0.0) if fade > 0 else 0.0

        state = TwinState(
            asset_id=self.asset_id, vehicle_type="EV", timestamp=latest.timestamp,
            metrics=metrics, derived=derived,
        )
        state.findings = self.check_thresholds(state)
        return state

    def predict_failure(self, state: TwinState, horizon_days: int) -> FailurePrediction:
        soh = state.metrics.get("soh") or 100.0
        fade = state.derived.get("fade_pct_per_cycle", _FALLBACK_FADE_PCT_PER_CYCLE)
        rate = state.derived.get("daily_cycle_rate", _DEFAULT_DAILY_CYCLE_RATE)

        projected_soh = max(soh - fade * rate * horizon_days, 0.0)
        per_day_loss = fade * rate
        days_to_threshold = (soh - _SOH_FAILURE_THRESHOLD) / per_day_loss if per_day_loss > 0 and soh > _SOH_FAILURE_THRESHOLD else None

        risk_level, risk_numeric = _risk_from(state, projected_soh)
        ambient = state.metrics.get("ambient_temp")
        explanation = (
            f"SOH is {soh:.1f}% (capacity {state.metrics.get('capacity_ah') or 0:.2f} Ah of 2.00 Ah rated). "
            f"The fitted fade rate for ~{ambient if ambient is not None else '?'}°C ambient is {fade:.2f}% per cycle; at an assumed "
            f"{rate:.1f} cycle/day, projected SOH in {horizon_days} days is {projected_soh:.1f}%."
        )
        if days_to_threshold is not None:
            explanation += f" Estimated {days_to_threshold:.0f} days (~{days_to_threshold * rate:.0f} cycles) until SOH reaches the {_SOH_FAILURE_THRESHOLD:.0f}% end-of-life threshold."

        return FailurePrediction(
            asset_id=self.asset_id, horizon_days=horizon_days, risk_score=risk_level,
            risk_score_numeric=risk_numeric, predicted_failure_horizon_days=days_to_threshold,
            explanation=explanation,
        )

    def simulate(self, state: TwinState, hypothetical_params: dict[str, float], horizon_days: int) -> TwinState:
        projected = deepcopy(state)
        projected.timestamp = state.timestamp + timedelta(days=horizon_days)

        rate = hypothetical_params.get("daily_cycle_rate", state.derived.get("daily_cycle_rate", _DEFAULT_DAILY_CYCLE_RATE))
        temp_delta = hypothetical_params.get("avg_temp_delta", 0.0)
        fade = fade_per_cycle(state.metrics.get("ambient_temp"), temp_delta)

        cycles = rate * horizon_days
        soh = state.metrics.get("soh") or 100.0
        projected.metrics["soh"] = max(soh - fade * cycles, 0.0)
        projected.metrics["charge_cycles"] = (state.metrics.get("charge_cycles") or 0) + cycles
        if projected.metrics.get("battery_temp") is not None:
            projected.metrics["battery_temp"] += temp_delta
        projected.derived.update(daily_cycle_rate=rate, fade_pct_per_cycle=fade)
        projected.findings = self.check_thresholds(projected)
        return projected


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
