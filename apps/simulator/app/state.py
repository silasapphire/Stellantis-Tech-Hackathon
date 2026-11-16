from __future__ import annotations

from datetime import datetime, timezone

from app.fault_injection import FAULT_PRESETS, ActiveFault
from app.replay import DatasetReplayer

_ROUND_FIELDS = {"soc", "soh", "capacity_ah", "cell_voltage", "current", "battery_temp", "coolant_temp",
                 "control_module_voltage", "intake_air_temp"}


class ReplayAsset:
    """One fleet asset: a dataset replayer plus the optional demo fault overlay."""

    def __init__(self, asset_id: str, name: str, vehicle_type: str, replayer: DatasetReplayer):
        self.asset_id = asset_id
        self.name = name
        self.vehicle_type = vehicle_type
        self.replayer = replayer
        self.metrics: dict = {}
        self.active_fault: ActiveFault | None = None

    def inject_fault(self, fault_type: str, target_value: float | None = None, ramp_ticks: int | None = None) -> None:
        preset = FAULT_PRESETS.get(fault_type)
        if preset is None:
            raise ValueError(f"unknown fault_type: {fault_type}")
        if preset.vehicle_type != self.vehicle_type:
            raise ValueError(f"{fault_type} applies to {preset.vehicle_type} assets, not {self.vehicle_type}")
        self.active_fault = ActiveFault(
            fault_type=fault_type, preset=preset,
            target_value=preset.target_value if target_value is None else target_value,
            ramp_ticks=max(1, ramp_ticks if ramp_ticks is not None else preset.ramp_ticks),
        )

    def clear_fault(self) -> bool:
        """Start ramping an injected fault away. Returns False when there was nothing injected."""
        if self.active_fault is None:
            return False
        self.active_fault.clearing = True
        self.active_fault.clear_start_value = self.metrics.get(self.active_fault.preset.field, 0.0)
        self.active_fault.elapsed_ticks = 0
        return True

    @property
    def fault_status(self) -> dict | None:
        f = self.active_fault
        if f is None:
            return None
        return {
            "fault_type": f.fault_type, "field": f.preset.field, "target_value": f.target_value,
            "clearing": f.clearing, "elapsed_ticks": f.elapsed_ticks, "ramp_ticks": f.ramp_ticks,
            "progress": round(min(f.elapsed_ticks / max(f.ramp_ticks, 1), 1.0), 3),
        }

    def tick(self) -> dict:
        self.metrics = dict(self.replayer.next())
        fault = self.active_fault
        if fault is not None:
            field = fault.preset.field
            if field in self.metrics:
                self.metrics[field] = fault.ramp_value(self.metrics[field])
            fault.elapsed_ticks += 1
            if fault.is_recovered():
                self.active_fault = None
        payload = {"asset_id": self.asset_id, "timestamp": datetime.now(timezone.utc).isoformat()}
        for k, v in self.metrics.items():
            payload[k] = round(v, 3) if k in _ROUND_FIELDS and isinstance(v, float) else v
        return payload
