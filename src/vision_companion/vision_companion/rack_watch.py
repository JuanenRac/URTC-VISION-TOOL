# =============================================================================
# URTC-VISION-TOOL - vision_companion thermal watch of the tool rack over time: rack_watch.py
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
# rack_check.py judges one frame. This module closes the loop of the Smart Idle pre-heat: it judges a series of frames taken while the
# rack heats the tips, tells when each slot reached its target, and answers the question that matters before a swap: is the tip of this
# slot stable at its target and free of faults? It also holds a simulator of the rack and its camera (a first-order heating curve per
# slot, a few faults) so the whole loop is tested without a camera or a rack. Nothing here commands the rack: the answer goes to a
# person or to the host, which decides. Nothing has been checked on a real rack; the time constants are estimates for a soldering tip.
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from . import rack_check
from .alignment import BoundingBox, rgb_roi_to_thermal_roi
from .rack_check import RackCheckError

STABLE_SAMPLES = 3                 # consecutive readings at the target before a swap is allowed
SCENARIOS = ("healthy", "slow_heater", "overshoot", "heater_in_empty_slot", "dead_region")
AMBIENT_C = 24.0
TAU_MS = 12_000.0                  # first-order heating time constant of a healthy tip
SLOW_TAU_MS = 80_000.0


@dataclass
class SlotHistory:
    slot: int
    occupied: bool
    target_c: int
    verdicts: list[str] = field(default_factory=list)
    reached_at_ms: int | None = None

    @property
    def final(self) -> str:
        return self.verdicts[-1] if self.verdicts else rack_check.UNKNOWN

    @property
    def swap_state(self) -> str:
        """``swap_ok``, ``swap_wait`` or ``swap_blocked`` (the text key): a swap needs the last readings all at the target."""
        if self.final in rack_check.FAULTS:
            return "swap_blocked"
        tail = self.verdicts[-STABLE_SAMPLES:]
        wanted = rack_check.REACHED if self.occupied and self.target_c else rack_check.IDLE_OK
        if len(tail) == STABLE_SAMPLES and all(v == wanted for v in tail):
            return "swap_ok"
        return "swap_wait"


def watch(frames: np.ndarray, state: dict[str, Any], rgb_width: int, rgb_height: int, interval_ms: int,
          ambient_c: float | None = None) -> list[SlotHistory]:
    """Judge a stack of frames ``(n, height, width)``, one every ``interval_ms`` from the moment the targets were set."""
    if frames.ndim != 3 or frames.shape[0] == 0:
        raise RackCheckError("the frames must be a stack of (height, width) frames")
    if isinstance(interval_ms, bool) or not isinstance(interval_ms, int) or interval_ms <= 0:
        raise RackCheckError("the interval must be a positive whole number of milliseconds")
    histories: dict[int, SlotHistory] = {}
    for index in range(frames.shape[0]):
        elapsed = index * interval_ms
        results = rack_check.check_rack(frames[index], dict(state, elapsed_ms=elapsed), rgb_width, rgb_height, ambient_c)
        for result in results:
            history = histories.setdefault(result.slot, SlotHistory(result.slot, result.occupied, result.commanded_c))
            history.verdicts.append(result.verdict)
            if history.reached_at_ms is None and result.verdict == rack_check.REACHED:
                history.reached_at_ms = elapsed
    return list(histories.values())


def histories_to_dict(histories: list[SlotHistory], interval_ms: int) -> dict[str, Any]:
    return {"schema": 1, "interval_ms": interval_ms, "faults": sum(1 for h in histories if h.final in rack_check.FAULTS),
            "slots": [{"slot": h.slot, "occupied": h.occupied, "target_c": h.target_c, "final": h.final, "reached_at_ms": h.reached_at_ms,
                       "swap": h.swap_state} for h in histories]}


def _thermal_cell(box: Any, rgb_width: int, rgb_height: int, width: int, height: int) -> tuple[int, int]:
    x0, y0, x1, y1 = box
    return (min(width - 1, max(0, int((x0 + x1) / 2 * width / rgb_width))), min(height - 1, max(0, int((y0 + y1) / 2 * height / rgb_height))))


def simulate(state: dict[str, Any], scenario: str, count: int, interval_ms: int, rgb_width: int, rgb_height: int,
             width: int = 32, height: int = 24, seed: int = 1) -> np.ndarray:
    """The thermal frames a camera looking at the rack would give while it heats, as a ``(count, height, width)`` stack.

    ``healthy``: every occupied slot follows a first-order curve to its target. ``slow_heater``: the first heated slot heats so slowly
    that it misses the time allowed. ``overshoot``: the first heated slot ends 40 C above its target. ``heater_in_empty_slot``: the
    first empty slot heats although no tool is in it. ``dead_region``: every pixel of the region of the first slot reads as failed."""
    if scenario not in SCENARIOS:
        raise RackCheckError(f"unknown scenario '{scenario}'; known: {', '.join(SCENARIOS)}")
    if count <= 0 or interval_ms <= 0:
        raise RackCheckError("count and interval must be positive")
    slots = state.get("slots") if isinstance(state, dict) else None
    if not isinstance(slots, list):
        raise RackCheckError("the state needs a list of slots")
    rng = np.random.default_rng(seed)
    frames = np.full((count, height, width), AMBIENT_C, dtype=np.float32)
    heated = [s for s in slots if s.get("occupied") and int(s.get("target_c", 0)) > 0]
    empty = [s for s in slots if not s.get("occupied")]
    for position, item in enumerate(slots):
        try:
            x, y = _thermal_cell(item["roi"], rgb_width, rgb_height, width, height)
        except (KeyError, TypeError, ValueError) as error:
            raise RackCheckError(f"a slot needs a roi [x0, y0, x1, y1]: {error}") from error
        target = float(item.get("target_c", 0)) if item.get("occupied") else 0.0
        tau, extra = TAU_MS, 0.0
        if scenario == "slow_heater" and heated and item is heated[0]:
            tau = SLOW_TAU_MS
        if scenario == "overshoot" and heated and item is heated[0]:
            extra = 40.0
        if scenario == "heater_in_empty_slot" and empty and item is empty[0]:
            target = 150.0
        for index in range(count):
            t = index * interval_ms
            frames[index, y, x] = AMBIENT_C + (target + extra - AMBIENT_C) * (1.0 - math.exp(-t / tau)) if target > 0 else AMBIENT_C
        if scenario == "dead_region" and position == 0:
            box = rgb_roi_to_thermal_roi(BoundingBox(*item["roi"]), rgb_width, rgb_height, width, height)
            if box is not None:
                frames[:, box.y0:box.y1, box.x0:box.x1] = np.nan
    frames += (rng.normal(0.0, 0.15, size=frames.shape) * np.isfinite(frames)).astype(np.float32)
    return frames
