from __future__ import annotations

from common.schemas import VehicleType

_EV_SIGNAL_FIELDS = {"soc", "soh", "cell_voltage", "battery_temp"}
_ICE_SIGNAL_FIELDS = {"rpm", "load_pct", "dtc_count"}


def detect_vehicle_type(sample_reading: dict) -> VehicleType | None:
    """Auto-detect vehicle type from a raw telemetry payload's populated fields."""
    present = {k for k, v in sample_reading.items() if v is not None}
    if present & _EV_SIGNAL_FIELDS:
        return VehicleType.EV
    if present & _ICE_SIGNAL_FIELDS:
        return VehicleType.ICE
    return None
