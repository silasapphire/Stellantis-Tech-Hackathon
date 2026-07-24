from __future__ import annotations

import operator as op
from abc import ABC, abstractmethod
from datetime import datetime, timezone

from app.models import FaultFinding, FaultRule, FailurePrediction, TwinState
from common.schemas import TelemetryReading

_OPERATORS = {">": op.gt, "<": op.lt}


class DigitalTwin(ABC):
    """Common interface every vehicle-specific twin implements.

    Subclasses supply the field set that matters for their vehicle type and the
    numeric models behind predict_failure/simulate; threshold evaluation against
    the fault library is shared here since it's identical logic regardless of
    which fields are being checked.
    """

    def __init__(self, asset_id: str, fault_library: list[FaultRule]):
        self.asset_id = asset_id
        self.fault_library = fault_library

    @abstractmethod
    def get_state(self, readings: list[TelemetryReading]) -> TwinState:
        """Turn raw telemetry (most recent first) into modeled twin state."""

    @abstractmethod
    def predict_failure(self, state: TwinState, horizon_days: int) -> FailurePrediction:
        """Project forward and estimate a failure risk/horizon from current state."""

    @abstractmethod
    def simulate(
        self, state: TwinState, hypothetical_params: dict[str, float], horizon_days: int
    ) -> TwinState:
        """Run the twin forward under hypothetical operating conditions."""

    def check_thresholds(self, state: TwinState) -> list[FaultFinding]:
        findings: list[FaultFinding] = []
        for rule in self.fault_library:
            value = state.metrics.get(rule.field)
            if value is None:
                continue
            comparator = _OPERATORS[rule.operator]
            if comparator(value, rule.threshold):
                findings.append(
                    FaultFinding(
                        fault_id=rule.id,
                        type=rule.type,
                        severity=rule.severity,
                        field=rule.field,
                        value=float(value),
                        threshold=rule.threshold,
                        operator=rule.operator,
                        message=rule.message.format(value=value, threshold=rule.threshold),
                    )
                )
        return findings

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)
