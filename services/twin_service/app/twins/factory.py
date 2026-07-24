from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.models import FaultRule
from app.twins.base import DigitalTwin
from app.twins.engine_twin import EngineTwin
from app.twins.ev_twin import EVTwin
from common.schemas import VehicleType
from common.vehicle_detection import detect_vehicle_type as detect_vehicle_type  # re-exported

_FAULT_LIBRARY_DIR = Path(__file__).resolve().parent.parent / "fault_library"


@lru_cache(maxsize=2)
def _load_fault_library(filename: str) -> tuple[FaultRule, ...]:
    with open(_FAULT_LIBRARY_DIR / filename, encoding="utf-8") as f:
        rules = json.load(f)
    return tuple(FaultRule(**rule) for rule in rules)


def get_twin(vehicle_type: VehicleType | str, asset_id: str) -> DigitalTwin:
    vehicle_type = VehicleType(vehicle_type)
    if vehicle_type is VehicleType.EV:
        return EVTwin(asset_id, list(_load_fault_library("ev_faults.json")))
    if vehicle_type is VehicleType.ICE:
        return EngineTwin(asset_id, list(_load_fault_library("ice_faults.json")))
    raise ValueError(f"unknown vehicle_type: {vehicle_type}")
