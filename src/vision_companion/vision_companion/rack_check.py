# =============================================================================
# URTC-VISION-TOOL - vision_companion thermal check of the tool rack: rack_check.py
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
# A thermal camera that looks at the tips in the tool rack reads one temperature per slot. This module judges that reading against
# what the rack ordered: has the tip reached its target, is it too slow, is it too hot, is a heater on in a slot that has no tool in
# it. The rules are those of URTC-SMART-RACK (src/slot_verify.c) and of the rack model of URTC-COMMON; a shared set of cases is
# reproduced by the three. Nothing here commands the rack: the verdicts go to a person or to the host. Nothing has been checked on a
# real rack: the limits are estimates for a soldering tip.
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any

import numpy as np

from .alignment import BoundingBox, analyze_rgb_roi

UNKNOWN, EMPTY_OK, EMPTY_HOT, IDLE_OK, IDLE_HOT, HEATING, REACHED, NOT_REACHED, OVERSHOOT = (
    "unknown", "empty_ok", "heater_in_empty_slot", "idle_ok", "still_hot", "heating", "reached", "not_reached", "overshoot")
FAULTS = {EMPTY_HOT, IDLE_HOT, NOT_REACHED, OVERSHOOT}
TOLERANCE_C, OVERSHOOT_C, EMPTY_HOT_C, IDLE_HOT_C, REACH_TIMEOUT_MS = 15.0, 25.0, 40.0, 60.0, 60_000


class RackCheckError(ValueError):
    """The rack plan or state is not usable."""


def verify_slot(occupied: bool, commanded_c: float, measured_c: float | None, ambient_c: float, elapsed_ms: int) -> str:
    """What the thermal reading of a slot says about the pre-heat that was ordered (same rules as slot_verify.c)."""
    if measured_c is None or (isinstance(measured_c, float) and math.isnan(measured_c)):
        return UNKNOWN
    if not occupied:
        return EMPTY_HOT if measured_c > ambient_c + EMPTY_HOT_C else EMPTY_OK
    if commanded_c == 0:
        return IDLE_HOT if measured_c > ambient_c + IDLE_HOT_C else IDLE_OK
    if measured_c > commanded_c + OVERSHOOT_C:
        return OVERSHOOT
    if measured_c >= commanded_c - TOLERANCE_C:
        return REACHED
    return NOT_REACHED if elapsed_ms >= REACH_TIMEOUT_MS else HEATING


@dataclass(frozen=True)
class SlotResult:
    slot: int
    occupied: bool
    commanded_c: int
    measured_c: float | None
    verdict: str

    @property
    def is_fault(self) -> bool:
        return self.verdict in FAULTS


def check_rack(thermal: np.ndarray, state: dict[str, Any], rgb_width: int, rgb_height: int, ambient_c: float | None = None) -> list[SlotResult]:
    """Judge every slot of a rack state. ``state`` is ``{"elapsed_ms": n, "slots": [{"slot", "roi": [x0, y0, x1, y1], "occupied", "target_c"}]}``
    where the region is where the tip of that slot is in the RGB image. The temperature of a slot is the hottest valid pixel of its region."""
    if not isinstance(state, dict) or not isinstance(state.get("slots"), list):
        raise RackCheckError("the state needs a list of slots")
    finite = thermal[np.isfinite(thermal)]
    ambient = float(np.median(finite)) if ambient_c is None and finite.size else (24.0 if ambient_c is None else ambient_c)
    elapsed = state.get("elapsed_ms", 0)
    if isinstance(elapsed, bool) or not isinstance(elapsed, int) or elapsed < 0:
        raise RackCheckError("elapsed_ms must be a whole number of milliseconds")
    results = []
    for item in state["slots"]:
        try:
            box = BoundingBox(*item["roi"])
            slot, occupied, target = int(item["slot"]), bool(item["occupied"]), int(item.get("target_c", 0))
        except (KeyError, TypeError, ValueError) as error:
            raise RackCheckError(f"a slot needs slot, roi [x0, y0, x1, y1], occupied and target_c: {error}") from error
        stats = analyze_rgb_roi(thermal, box, rgb_width=rgb_width, rgb_height=rgb_height)
        measured = None if stats.is_empty else stats.max_c
        results.append(SlotResult(slot, occupied, target, measured, verify_slot(occupied, target, measured, ambient, elapsed)))
    return results


def results_to_dict(results: list[SlotResult], ambient_c: float | None = None) -> dict[str, Any]:
    return {"schema": 1, "ambient_c": ambient_c, "faults": sum(1 for r in results if r.is_fault),
            "slots": [{"slot": r.slot, "occupied": r.occupied, "target_c": r.commanded_c,
                       "measured_c": None if r.measured_c is None else round(r.measured_c, 2), "verdict": r.verdict, "fault": r.is_fault} for r in results]}


def load_state(path: str) -> dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError) as error:
        raise RackCheckError(f"cannot read the rack state: {error}") from error
