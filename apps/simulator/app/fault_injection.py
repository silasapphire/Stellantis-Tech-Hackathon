"""Optional demo overlay: inject a fault on top of the replayed real data.

Off by default - real data is replayed untouched. A preset ramps one field from its
current real value toward `target_value` over `ramp_ticks`, and ramps back to the real
value once cleared (which is how the demo shows an issue auto-resolving after a self-heal).
`lo`/`hi`/`unit`/`hint` only describe the preset to the UI's severity slider.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FaultPreset:
    field: str
    target_value: float
    vehicle_type: str
    label: str
    unit: str
    lo: float
    hi: float
    hint: str
    ramp_ticks: int = 12


FAULT_PRESETS: dict[str, FaultPreset] = {
    # EV (battery)
    "battery_overheat": FaultPreset("battery_temp", 50.0, "EV", "Battery overheat", "°C", 30, 60,
                                    "flags above 38 °C (medium), 45 °C (high)", 15),
    "battery_undervoltage": FaultPreset("cell_voltage", 1.8, "EV", "Cell undervoltage", "V", 1.5, 3.0,
                                        "flags below 2.0 V (high)", 10),
    "capacity_collapse": FaultPreset("soh", 68.0, "EV", "Capacity collapse (SOH)", "%", 60, 90,
                                     "flags below 80 % (medium), 72 % (high)", 20),
    # ICE
    "coolant_overheat": FaultPreset("coolant_temp", 112.0, "ICE", "Coolant overheat", "°C", 95, 125,
                                    "flags above 105 °C (high)", 15),
    "low_system_voltage": FaultPreset("control_module_voltage", 11.4, "ICE", "Low system voltage", "V", 10.0, 12.6,
                                      "flags below 12.6 V (medium)", 10),
    "hot_intake_air": FaultPreset("intake_air_temp", 75.0, "ICE", "Hot intake air", "°C", 55, 90,
                                  "flags above 60 °C (low)", 12),
}


@dataclass
class ActiveFault:
    fault_type: str
    preset: FaultPreset
    target_value: float
    ramp_ticks: int
    elapsed_ticks: int = 0
    clearing: bool = False
    clear_start_value: float = 0.0

    def ramp_value(self, real_value: float) -> float:
        span = max(self.ramp_ticks, 1)
        progress = min(self.elapsed_ticks / span, 1.0)
        if self.clearing:
            return self.clear_start_value + (real_value - self.clear_start_value) * progress
        return real_value + (self.target_value - real_value) * progress

    def is_recovered(self) -> bool:
        return self.clearing and self.elapsed_ticks >= self.ramp_ticks
