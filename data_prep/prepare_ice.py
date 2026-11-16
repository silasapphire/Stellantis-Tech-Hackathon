"""Prepare the ICE dataset (diesel OBD-II PIDs + one-hot DTC flags).

Source: data/MASTER_TRAIN_X.xlsx + data/MASTER_TEST_X.xlsx
        (https://github.com/AbouAbdallah-Lounis/OBD-Dataset)

Steps (each one is counted in data/processed/ice_prep_report.json):
  1. load train + test, tag each row with its split
  2. drop consecutive exact-duplicate rows (the logger sample-and-holds, ~77% of rows)
  3. convert the US-customary values in the spreadsheets to SI:
       ECT/IAT/AAT  degF -> degC      MAP/BARO  psi -> kPa      FRP  psi -> MPa
     (VSS is already km/h, RPM rpm, LOAD %, VPWR V)
  4. drop rows with physically impossible values
  5. collapse the 14 one-hot DTC columns into a `dtc_codes` list + `dtc_count`
  6. attribute each row to a vehicle from its DTC signature (the xlsx has no vehicle id;
     the README documents which DTCs belong to which vehicle)
  7. write data/processed/ice_obd_clean.csv
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data"
OUT = RAW / "processed"

DTC_COLS = ["P0000", "P0562", "P0113", "P0102", "P0403", "P0404", "P2562",
            "P0234", "P2015", "P2009", "P0107", "P0069", "P0089", "P0406"]

# DTC signature (set of active codes) -> vehicle, from the dataset README.
# P0000 = "no fault" marker. Three fault-free vehicles (Rodius, 308, Fiesta) are
# indistinguishable in this file, so they share one "healthy reference" id.
SIGNATURES: dict[frozenset, tuple[str, str]] = {
    frozenset({"P0000"}): ("ICE-HEALTHY", "Healthy diesel reference (Rodius / 308 / Fiesta)"),
    frozenset({"P0562"}): ("ICE-PEUGEOT-2008", "Peugeot 2008 (2022) 1.5L"),
    frozenset({"P0113", "P0102", "P2562"}): ("ICE-BERLINGO", "Citroën Berlingo (2014) 1.6L"),
    frozenset({"P0406", "P0234", "P0102", "P0113"}): ("ICE-EXPERT", "Peugeot Expert (2014) 2.0L"),
    frozenset({"P0403", "P0404", "P2015", "P2009"}): ("ICE-KIA-SPORTAGE", "Kia Sportage (2017) 2.0L"),
    frozenset({"P0107", "P0069", "P0089"}): ("ICE-CAPTIVA", "Chevrolet Captiva (2011) 2.0L"),
}


def f_to_c(f: pd.Series) -> pd.Series:
    return (f - 32.0) * 5.0 / 9.0


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report: dict = {}

    frames = []
    for name, split in (("MASTER_TRAIN_X.xlsx", "train"), ("MASTER_TEST_X.xlsx", "test")):
        df = pd.read_excel(RAW / name)
        df["split"] = split
        report[f"raw_rows_{split}"] = int(len(df))
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    report["raw_rows_total"] = int(len(df))
    report["missing_values"] = int(df.isna().sum().sum())
    df = df.dropna().reset_index(drop=True)

    # 2. sample-and-hold duplicates (only *consecutive* repeats, order is preserved)
    feature_cols = [c for c in df.columns if c != "split"]
    same_as_prev = (df[feature_cols].shift() == df[feature_cols]).all(axis=1)
    same_as_prev &= df["split"].shift() == df["split"]
    report["consecutive_duplicates_dropped"] = int(same_as_prev.sum())
    df = df[~same_as_prev].reset_index(drop=True)

    # 3. unit conversion
    clean = pd.DataFrame(
        {
            "load_pct": df["LOAD_PCT"],
            "coolant_temp": f_to_c(df["ECT"]).round(1),
            "map_kpa": (df["MAP"] * 6.89476).round(1),
            "rpm": df["RPM"],
            "speed_kph": df["VSS"].round(1),
            "intake_air_temp": f_to_c(df["IAT"]).round(1),
            "maf": df["MAF"],  # unit not documented in the xlsx (0-0.26); kept as-is
            "fuel_rail_pressure_mpa": (df["FRP"] * 0.00689476).round(2),
            "baro_kpa": (df["BARO"] * 6.89476).round(1),
            "control_module_voltage": df["VPWR"],
            "ambient_air_temp": f_to_c(df["AAT"]).round(1),
            "mode": df["Mode"],
            "split": df["split"],
        }
    )

    # 4. physical-range validation
    valid = (
        clean["coolant_temp"].between(-40, 150)
        & clean["rpm"].between(0, 8000)
        & clean["load_pct"].between(0, 100)
        & clean["speed_kph"].between(0, 300)
        & clean["control_module_voltage"].between(6, 20)
        & clean["map_kpa"].between(0, 500)
    )
    report["out_of_range_dropped"] = int((~valid).sum())

    # 5/6. DTC list + vehicle attribution
    active = df[DTC_COLS].astype(bool)
    dtc_lists = active.apply(lambda r: [c for c in DTC_COLS if r[c] and c != "P0000"], axis=1)
    sig = active.apply(lambda r: frozenset(c for c in DTC_COLS if r[c]), axis=1)
    clean["dtc_codes"] = dtc_lists.apply(lambda l: ";".join(l))
    clean["dtc_count"] = dtc_lists.apply(len)
    ids = sig.map(lambda s: SIGNATURES.get(s, ("ICE-UNLABELED", "Unlabeled segment"))[0])
    clean.insert(0, "vehicle_id", ids)

    clean = clean[valid].reset_index(drop=True)
    clean["row_idx"] = clean.groupby("vehicle_id").cumcount()

    clean.to_csv(OUT / "ice_obd_clean.csv", index=False)

    report["clean_rows"] = int(len(clean))
    report["rows_per_vehicle"] = clean["vehicle_id"].value_counts().to_dict()
    report["vehicle_names"] = {v: n for v, n in SIGNATURES.values()}
    report["vehicle_names"]["ICE-UNLABELED"] = "Rows with no DTC flag set at all (no P0000 marker) - excluded from the fleet"
    report["dtc_per_vehicle"] = {
        v: sorted({c for s in g["dtc_codes"] for c in s.split(";") if c}) for v, g in clean.groupby("vehicle_id")
    }
    report["feature_summary"] = json.loads(
        clean.drop(columns=["vehicle_id", "split", "dtc_codes", "row_idx"]).describe().round(2).to_json()
    )
    (OUT / "ice_prep_report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k != "feature_summary"}, indent=2))


if __name__ == "__main__":
    main()
