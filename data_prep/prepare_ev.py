"""Prepare the EV dataset (NASA Prognostics Center Li-ion battery aging, .mat files).

Source: data/1..6 BatteryAgingARC*/B00xx.mat

Outputs (data/processed/):
  ev_cycles.csv          one row per charge/discharge/impedance cycle, ALL batteries
  ev_samples.csv         within-cycle samples (downsampled) for the demo fleet batteries,
                         with coulomb-counted SOC and capacity-derived SOH attached
  ev_degradation.json    capacity-fade model fitted on the discharge cycles (per ambient temp)
  ev_prep_report.json    what was dropped and why

Cleaning rules:
  * discharge capacity must be finite and 0.2-2.5 Ah (a handful of runs are logged with
    near-zero capacity - the dataset README says the cause "has not been fully analyzed")
  * capacity spikes (>15% off the rolling median of neighbouring cycles) are dropped
  * cycles with fewer than 10 samples are dropped
  * SOH = capacity / 2.0 Ah rated * 100 (README: EOL = 30% fade, 2.0 -> 1.4 Ah)
  * SOC: coulomb counting. Discharge: 100 -> 0 over the cycle. Charge: starts where the
    previous discharge ended and integrates charge current against that battery's capacity.
  * the same battery id appears in folders 2 and 3 (B0025-28); the longer record is kept.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.io as sio
from scipy.stats import linregress

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data"
OUT = RAW / "processed"

RATED_AH = 2.0
SAMPLE_BATTERIES = ["B0005", "B0006", "B0007", "B0018"]  # the demo EV fleet (room temp, 2A discharge)
SAMPLE_STRIDE = 10
DROPPED_SAMPLES = [0]


def load_battery(path: Path) -> tuple[str, list[dict]]:
    mat = sio.loadmat(str(path), simplify_cells=True)
    key = next(k for k in mat if not k.startswith("__"))
    return key, list(mat[key]["cycle"])


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report: dict = {"dropped": {}}

    # 1. load every battery; keep the longer record when an id appears twice
    batteries: dict[str, tuple[Path, list[dict]]] = {}
    for path in sorted(RAW.glob("*/B*.mat")):
        bid, cycles = load_battery(path)
        if bid not in batteries or len(cycles) > len(batteries[bid][1]):
            batteries[bid] = (path, cycles)
    report["batteries"] = len(batteries)

    cycle_rows: list[dict] = []
    sample_frames: list[pd.DataFrame] = []
    dropped = {"bad_capacity": 0, "capacity_spike": 0, "too_few_samples": 0}

    for bid, (path, cycles) in sorted(batteries.items()):
        discharge_n = 0
        rows: list[dict] = []
        for idx, c in enumerate(cycles):
            kind = c["type"]
            amb = float(np.atleast_1d(c["ambient_temperature"])[0])
            d = c["data"]
            row = {"battery_id": bid, "cycle_idx": idx, "type": kind, "ambient_temp": amb,
                   "source_folder": path.parent.name}
            if kind == "impedance":
                row["re_ohm"] = float(np.real(d["Re"])) if np.size(d["Re"]) == 1 else np.nan
                row["rct_ohm"] = float(np.real(d["Rct"])) if np.size(d["Rct"]) == 1 else np.nan
                rows.append(row)
                continue
            v, i, t, tm = (np.atleast_1d(d[k]).astype(float) for k in
                           ("Voltage_measured", "Current_measured", "Temperature_measured", "Time"))
            if len(v) < 10:
                dropped["too_few_samples"] += 1
                continue
            row.update(n_samples=len(v), duration_s=float(tm[-1] - tm[0]),
                       v_mean=v.mean(), v_min=v.min(), v_max=v.max(), i_mean=i.mean(),
                       t_mean=t.mean(), t_max=t.max())
            if kind == "discharge":
                capv = np.atleast_1d(d["Capacity"]).astype(float)
                cap = float(capv[0]) if capv.size else float("nan")
                if not np.isfinite(cap) or not (0.2 <= cap <= 2.5):
                    dropped["bad_capacity"] += 1
                    continue
                discharge_n += 1
                row["capacity_ah"] = cap
            row["discharge_count"] = discharge_n
            rows.append(row)

        df = pd.DataFrame(rows)
        # capacity spike filter on the discharge series
        dis = df["type"] == "discharge"
        if dis.sum() >= 5:
            med = df.loc[dis, "capacity_ah"].rolling(5, center=True, min_periods=3).median()
            spike = (df.loc[dis, "capacity_ah"] - med).abs() / med > 0.15
            dropped["capacity_spike"] += int(spike.sum())
            df = df.drop(index=spike[spike].index)
        # capacity / SOH forward-filled onto charge + impedance rows so every row has a health value
        df["capacity_ah"] = df["capacity_ah"].ffill().bfill()
        df["soh_pct"] = (df["capacity_ah"] / RATED_AH * 100).clip(upper=100.0).round(2)  # fresh cells can exceed rated capacity
        df["discharge_count"] = df["discharge_count"].ffill().fillna(0).astype(int)
        cycle_rows.extend(df.to_dict("records"))

        if bid in SAMPLE_BATTERIES:
            keep = set(df["cycle_idx"])
            sample_frames.append(_samples(bid, cycles, df, keep))

    cycles_df = pd.DataFrame(cycle_rows)
    cycles_df.round(4).to_csv(OUT / "ev_cycles.csv", index=False)
    pd.concat(sample_frames, ignore_index=True).to_csv(OUT / "ev_samples.csv", index=False)

    # 2. capacity-fade model: SOH(%) vs discharge cycle number, per ambient temperature
    model: dict = {"rated_ah": RATED_AH, "eol_soh_pct": 70.0, "per_ambient_temp": {}}
    dis_df = cycles_df[cycles_df["type"] == "discharge"]
    for amb, g in dis_df.groupby("ambient_temp"):
        if len(g) < 20:
            continue
        slopes = []
        for _, b in g.groupby("battery_id"):
            if len(b) >= 20:
                r = linregress(b["discharge_count"], b["soh_pct"])
                slopes.append(r.slope)
        if slopes:
            model["per_ambient_temp"][str(int(amb))] = {
                "fade_pct_per_cycle": float(-np.median(slopes)), "n_batteries": len(slopes)}
    allslopes = [v["fade_pct_per_cycle"] for v in model["per_ambient_temp"].values()]
    model["default_fade_pct_per_cycle"] = float(np.median(allslopes)) if allslopes else 0.2
    (OUT / "ev_degradation.json").write_text(json.dumps(model, indent=2))

    report["dropped"] = dropped
    report["cycles_total"] = int(len(cycles_df))
    report["cycles_by_type"] = cycles_df["type"].value_counts().to_dict()
    report["invalid_samples_dropped"] = DROPPED_SAMPLES[0]
    report["sample_rows"] = int(sum(len(f) for f in sample_frames))
    report["sample_batteries"] = SAMPLE_BATTERIES
    report["degradation_model"] = model
    (OUT / "ev_prep_report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


def _samples(bid: str, cycles: list[dict], df: pd.DataFrame, keep: set[int]) -> pd.DataFrame:
    meta = df.set_index("cycle_idx")
    out: list[pd.DataFrame] = []
    soc_after_discharge = None
    for idx, c in enumerate(cycles):
        if idx not in keep or c["type"] == "impedance":
            continue
        d = c["data"]
        v, i, t, tm = (np.atleast_1d(d[k]).astype(float) for k in
                       ("Voltage_measured", "Current_measured", "Temperature_measured", "Time"))
        cap = float(meta.loc[idx, "capacity_ah"])
        dt = np.diff(tm, prepend=tm[0])
        ah = np.cumsum(np.abs(i) * dt) / 3600.0  # cumulative Ah moved
        if c["type"] == "discharge":
            soc = np.clip(100.0 * (1.0 - ah / max(cap, 1e-6)), 0, 100)
            soc_after_discharge = float(soc[-1])
        else:
            # first charge has no preceding discharge: estimate the start SOC from voltage (3.0 V -> 0%, 4.2 V -> 100%)
            start = soc_after_discharge if soc_after_discharge is not None else float(np.clip((v[0] - 3.0) / 1.2 * 100, 0, 100))
            soc = np.clip(start + 100.0 * ah / max(cap, 1e-6), 0, 100)
        sl = slice(None, None, SAMPLE_STRIDE)
        frame = pd.DataFrame({
            "battery_id": bid, "cycle_idx": idx, "phase": c["type"],
            "discharge_count": int(meta.loc[idx, "discharge_count"]),
            "t_s": tm[sl].round(1), "cell_voltage": v[sl].round(4), "current": i[sl].round(4),
            "battery_temp": t[sl].round(2), "ambient_temp": float(meta.loc[idx, "ambient_temp"]),
            "soc": soc[sl].round(2), "soh": float(meta.loc[idx, "soh_pct"]),
            "capacity_ah": cap,
        })
        # drop physically impossible samples (sensor glitches, e.g. 8 V on a 4.2 V cell)
        ok = frame["cell_voltage"].between(1.5, 4.5) & frame["battery_temp"].between(-10, 80) & frame["soc"].notna()
        DROPPED_SAMPLES[0] += int((~ok).sum())
        out.append(frame[ok])
    return pd.concat(out, ignore_index=True)


if __name__ == "__main__":
    main()
