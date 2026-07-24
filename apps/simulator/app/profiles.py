"""Baseline operating values and per-tick noise for synthetic telemetry."""
from __future__ import annotations

# field -> (baseline, noise_stddev)
EV_BASELINE: dict[str, tuple[float, float]] = {
    "soc": (80.0, 0.5),
    "soh": (97.0, 0.02),
    "pack_voltage": (380.0, 2.0),
    "cell_temp_spread": (2.0, 0.3),
    "motor_temp": (60.0, 2.0),
    "inverter_temp": (50.0, 2.0),
    "coolant_temp": (40.0, 1.5),
    "charge_rate": (0.0, 0.0),  # driven explicitly by the charging cycle, not noise
}

ICE_BASELINE: dict[str, tuple[float, float]] = {
    "rpm": (1500.0, 50.0),
    "oil_pressure": (40.0, 1.0),
    "oil_temp": (90.0, 2.0),
    "coolant_temp": (85.0, 2.0),
    "vibration_index": (2.5, 0.2),
    "fuel_rate": (5.0, 0.3),
    "air_fuel_ratio_proxy": (1.0, 0.02),
}

EV_SOC_DRIFT_PER_TICK = -0.15  # slow discharge while "driving"
EV_CHARGE_CYCLE_TICKS = 180  # roughly one charge cycle worth of ticks between charges
EV_CHARGE_DURATION_TICKS = 20
