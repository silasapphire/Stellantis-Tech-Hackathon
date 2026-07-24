"""Injectable fault presets: each ramps one telemetry field toward a target value
over `ramp_ticks`, and ramps back to baseline over the same span once cleared -
which is what lets the demo show an issue auto-clearing as telemetry recovers.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FaultPreset:
    field: str
    target_value: float
    ramp_ticks: int = 12


FAULT_PRESETS: dict[str, FaultPreset] = {
    # EV
    "battery_overheat": FaultPreset(field="cell_temp_spread", target_value=12.0, ramp_ticks=15),
    "motor_overtemp": FaultPreset(field="motor_temp", target_value=135.0, ramp_ticks=15),
    "inverter_overtemp": FaultPreset(field="inverter_temp", target_value=115.0, ramp_ticks=15),
    "low_soh": FaultPreset(field="soh", target_value=75.0, ramp_ticks=25),
    # ICE
    "oil_pressure_drop": FaultPreset(field="oil_pressure", target_value=12.0, ramp_ticks=12),
    "coolant_overheat": FaultPreset(field="coolant_temp", target_value=112.0, ramp_ticks=15),
    "high_vibration": FaultPreset(field="vibration_index", target_value=9.0, ramp_ticks=12),
    "misfire": FaultPreset(field="misfire_count", target_value=8.0, ramp_ticks=8),
}


@dataclass
class ActiveFault:
    fault_type: str
    preset: FaultPreset
    elapsed_ticks: int = 0
    clearing: bool = False
    clear_start_value: float = 0.0

    def ramp_value(self, baseline: float) -> float:
        span = max(self.preset.ramp_ticks, 1)
        progress = min(self.elapsed_ticks / span, 1.0)
        if self.clearing:
            return self.clear_start_value + (baseline - self.clear_start_value) * progress
        return baseline + (self.preset.target_value - baseline) * progress

    def is_recovered(self) -> bool:
        return self.clearing and self.elapsed_ticks >= self.preset.ramp_ticks
