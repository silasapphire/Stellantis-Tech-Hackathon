"""Replay of the *prepared real datasets* (data/processed/*.csv) as live telemetry.

  ICE: ice_obd_clean.csv  - OBD-II PIDs + active DTCs, one vehicle per asset
  EV : ev_samples.csv     - NASA Li-ion cell charge/discharge samples, one cell per asset

Nothing here is synthesised: every value comes from a dataset row. Run
`python data_prep/prepare_ice.py` and `python data_prep/prepare_ev.py` first.
"""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[3]
PROCESSED = Path(os.environ.get("PROCESSED_DATA_DIR", _REPO_ROOT / "data" / "processed"))

_ICE_FIELDS = [
    "load_pct", "coolant_temp", "map_kpa", "rpm", "speed_kph", "intake_air_temp", "maf",
    "fuel_rail_pressure_mpa", "baro_kpa", "control_module_voltage", "ambient_air_temp",
]


class DatasetReplayer:
    """Steps through one vehicle's/cell's rows in order, looping at the end."""

    def __init__(self, rows: list[dict], start_fraction: float = 0.0, rows_per_tick: int = 1):
        if not rows:
            raise ValueError("no rows to replay")
        self.rows = rows
        self.rows_per_tick = max(1, rows_per_tick)
        self._i = int(len(rows) * min(max(start_fraction, 0.0), 0.99))

    @property
    def position(self) -> float:
        return self._i / len(self.rows)

    def next(self) -> dict:
        row = self.rows[self._i]
        self._i = (self._i + self.rows_per_tick) % len(self.rows)
        return row

    # -- constructors -------------------------------------------------------------------
    @classmethod
    def for_ice(cls, vehicle_id: str, start_fraction: float = 0.0, rows_per_tick: int = 1) -> "DatasetReplayer":
        df = pd.read_csv(PROCESSED / "ice_obd_clean.csv", keep_default_na=False)
        df = df[df["vehicle_id"] == vehicle_id].sort_values("row_idx")
        rows = []
        for r in df.to_dict("records"):
            reading = {f: float(r[f]) for f in _ICE_FIELDS}
            reading["drive_mode"] = int(r["mode"])
            reading["dtc_codes"] = [c for c in str(r["dtc_codes"]).split(";") if c]
            reading["dtc_count"] = int(r["dtc_count"])
            rows.append(reading)
        return cls(rows, start_fraction, rows_per_tick)

    @classmethod
    def for_ev(cls, battery_id: str, start_fraction: float = 0.0, rows_per_tick: int = 3) -> "DatasetReplayer":
        df = pd.read_csv(PROCESSED / "ev_samples.csv")
        df = df[df["battery_id"] == battery_id]
        rows = [
            {
                "soc": float(r.soc), "soh": float(r.soh), "capacity_ah": float(r.capacity_ah),
                "cell_voltage": float(r.cell_voltage), "current": float(r.current),
                "battery_temp": float(r.battery_temp), "ambient_temp": float(r.ambient_temp),
                "charge_cycles": int(r.discharge_count), "phase": str(r.phase),
            }
            for r in df.itertuples()
        ]
        return cls(rows, start_fraction, rows_per_tick)
