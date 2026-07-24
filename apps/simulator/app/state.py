from __future__ import annotations

from datetime import datetime, timezone

import numpy as np

from app.fault_injection import FAULT_PRESETS, ActiveFault, FaultPreset
from app.profiles import (
    EV_BASELINE,
    EV_CHARGE_CYCLE_TICKS,
    EV_CHARGE_DURATION_TICKS,
    EV_SOC_DRIFT_PER_TICK,
    ICE_BASELINE,
)

_INT_FIELDS = {"charge_cycles", "misfire_count"}


class SimulatedAsset:
    def __init__(self, asset_id: str, name: str, vehicle_type: str):
        self.asset_id = asset_id
        self.name = name
        self.vehicle_type = vehicle_type
        self.baseline = dict(EV_BASELINE) if vehicle_type == "EV" else dict(ICE_BASELINE)
        self.metrics: dict[str, float] = {field: base for field, (base, _) in self.baseline.items()}

        if vehicle_type == "EV":
            self.metrics["charge_cycles"] = 120.0
            self._charging = False
            self._ticks_to_next_charge = EV_CHARGE_CYCLE_TICKS
            self._charge_ticks_remaining = 0
        else:
            self.metrics["misfire_count"] = 0.0

        self.active_fault: ActiveFault | None = None
        self.rng = np.random.default_rng()

    def inject_fault(self, fault_type: str) -> None:
        preset = FAULT_PRESETS.get(fault_type)
        if preset is None:
            raise ValueError(f"unknown fault_type: {fault_type}")
        self.active_fault = ActiveFault(fault_type=fault_type, preset=preset)

    def clear_fault(self) -> None:
        if self.active_fault is None:
            return
        self.active_fault.clearing = True
        self.active_fault.clear_start_value = self.metrics.get(self.active_fault.preset.field, 0.0)
        self.active_fault.elapsed_ticks = 0

    @property
    def fault_status(self) -> dict | None:
        if self.active_fault is None:
            return None
        return {
            "fault_type": self.active_fault.fault_type,
            "field": self.active_fault.preset.field,
            "clearing": self.active_fault.clearing,
            "elapsed_ticks": self.active_fault.elapsed_ticks,
        }

    def tick(self) -> dict:
        self._random_walk()
        if self.vehicle_type == "EV":
            self._tick_ev_cycle()
        self._apply_fault()
        return self._reading_payload()

    def _random_walk(self) -> None:
        for field, (base, noise) in self.baseline.items():
            if noise == 0:
                continue
            current = self.metrics.get(field, base)
            reverted = current + (base - current) * 0.05  # gentle mean reversion
            self.metrics[field] = reverted + self.rng.normal(0, noise)

    def _tick_ev_cycle(self) -> None:
        if self._charging:
            self.metrics["charge_rate"] = 60.0 + self.rng.normal(0, 5)
            self.metrics["soc"] = min(self.metrics["soc"] + 4.0, 100.0)
            self._charge_ticks_remaining -= 1
            if self._charge_ticks_remaining <= 0 or self.metrics["soc"] >= 100.0:
                self._charging = False
                self.metrics["charge_rate"] = 0.0
                self.metrics["charge_cycles"] += 1
                self.metrics["soh"] = max(self.metrics["soh"] - 0.03, 0.0)
                self._ticks_to_next_charge = EV_CHARGE_CYCLE_TICKS
        else:
            self.metrics["soc"] = max(self.metrics["soc"] + EV_SOC_DRIFT_PER_TICK, 5.0)
            self.metrics["charge_rate"] = 0.0
            self._ticks_to_next_charge -= 1
            if self._ticks_to_next_charge <= 0 or self.metrics["soc"] <= 15.0:
                self._charging = True
                self._charge_ticks_remaining = EV_CHARGE_DURATION_TICKS

    def _apply_fault(self) -> None:
        fault = self.active_fault
        if fault is None:
            return

        baseline_value = self.baseline.get(fault.preset.field, (0.0, 0.0))[0]
        self.metrics[fault.preset.field] = fault.ramp_value(baseline_value)
        fault.elapsed_ticks += 1

        if fault.is_recovered():
            self.metrics[fault.preset.field] = baseline_value
            self.active_fault = None

    def _reading_payload(self) -> dict:
        payload = {
            "asset_id": self.asset_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        for field, value in self.metrics.items():
            payload[field] = int(round(value)) if field in _INT_FIELDS else round(float(value), 2)
        return payload
