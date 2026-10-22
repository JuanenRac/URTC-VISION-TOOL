# =============================================================================
# URTC-VISION-TOOL - vision_companion drift of the thermal sensor: sensor_drift.py
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
# A reference scene (a wall at room temperature, filling the field of view) shows two things: pixels that no
# longer work, and an offset that moves with time. Several frames of the scene are reduced to a baseline (the mean of
# every pixel, the ambient it was taken at, the dead pixels); a later set of frames of the same scene is compared with it.
# The answer says what changed and, if the user wants it, writes a calibration file that the other commands accept.
# The scene must really be uniform and at a stable temperature: this module cannot tell a warm wall from a drifting sensor.
from __future__ import annotations

import json
import math
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

SCHEMA = 1
OK, DRIFT, DEAD, DRIFT_AND_DEAD = "ok", "drift", "dead_pixels", "drift_and_dead_pixels"
MIN_FRAMES = 4
_NOISE_FLOOR_C = 0.05


def _nanmean(stack: np.ndarray) -> np.ndarray:
    """Mean over the frames of every pixel, ignoring NaN; a pixel that never read a number is NaN (no warning for it)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return np.nanmean(np.where(np.isfinite(stack), stack, np.nan), axis=0)


def _nanstd(stack: np.ndarray) -> np.ndarray:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return np.nanstd(np.where(np.isfinite(stack), stack, np.nan), axis=0)


class DriftError(ValueError):
    """The frames or the baseline are not usable."""


@dataclass(frozen=True)
class Baseline:
    width: int
    height: int
    ambient_c: float
    mean_c: np.ndarray                  # (height, width), NaN where the pixel was dead
    dead_pixels: tuple[tuple[int, int], ...]

    def to_dict(self) -> dict[str, Any]:
        rows = [[None if not math.isfinite(v) else round(float(v), 4) for v in row] for row in self.mean_c]
        return {"schema": SCHEMA, "width": self.width, "height": self.height, "ambient_c": self.ambient_c,
                "mean_c": rows, "dead_pixels": [list(p) for p in self.dead_pixels]}


@dataclass(frozen=True)
class DriftReport:
    verdict: str
    offset_shift_c: float               # median change of all working pixels
    worst_pixel_shift_c: float          # the largest change of one working pixel after removing the common shift
    new_dead_pixels: tuple[tuple[int, int], ...]
    recovered_pixels: tuple[tuple[int, int], ...]
    frames: int


def _stack(frames: Any) -> np.ndarray:
    stack = np.asarray(frames, dtype=np.float64)
    if stack.ndim == 2:
        stack = stack[None, :, :]
    if stack.ndim != 3:
        raise DriftError("the frames must be (height, width) or (count, height, width)")
    if stack.shape[0] < MIN_FRAMES:
        raise DriftError(f"at least {MIN_FRAMES} frames of the reference scene are needed, got {stack.shape[0]}")
    return stack


def find_dead_pixels(stack: np.ndarray, outlier_c: float = 3.0, max_noise_c: float = 2.0) -> tuple[tuple[int, int], ...]:
    """Pixels that never read a number, that never change while the others do, that are far from their neighbours' level, or that are too noisy."""
    finite = np.isfinite(stack)
    dead = ~finite.all(axis=0)                                    # at least one frame without a number
    with np.errstate(invalid="ignore"):
        mean = _nanmean(stack)
        std = _nanstd(stack)
    good_std = std[~dead]
    typical = float(np.median(good_std)) if good_std.size else 0.0
    if typical > _NOISE_FLOOR_C / 4:
        dead |= std == 0.0                                        # stuck: no noise at all where every other pixel has some
    dead |= std > max_noise_c
    level = float(np.nanmedian(np.where(dead, np.nan, mean))) if (~dead).any() else math.nan
    spread = 1.4826 * float(np.nanmedian(np.abs(np.where(dead, np.nan, mean) - level))) if (~dead).any() else 0.0
    if math.isfinite(level):
        dead |= np.abs(mean - level) > max(outlier_c, 6.0 * spread)
    ys, xs = np.nonzero(dead)
    return tuple(sorted((int(x), int(y)) for x, y in zip(xs, ys, strict=True)))


def make_baseline(frames: Any, ambient_c: float | None = None) -> Baseline:
    stack = _stack(frames)
    dead = find_dead_pixels(stack)
    with np.errstate(invalid="ignore"):
        mean = _nanmean(stack)
    for x, y in dead:
        mean[y, x] = math.nan
    working = mean[np.isfinite(mean)]
    if working.size == 0:
        raise DriftError("every pixel is dead")
    ambient = float(np.median(working)) if ambient_c is None else float(ambient_c)
    return Baseline(stack.shape[2], stack.shape[1], ambient, mean, dead)


def compare(baseline: Baseline, frames: Any, offset_tolerance_c: float = 0.5, pixel_tolerance_c: float = 1.0) -> DriftReport:
    stack = _stack(frames)
    if stack.shape[1:] != (baseline.height, baseline.width):
        raise DriftError(f"the frames are {stack.shape[2]}x{stack.shape[1]} but the baseline is {baseline.width}x{baseline.height}")
    dead_now = set(find_dead_pixels(stack))
    dead_then = set(baseline.dead_pixels)
    with np.errstate(invalid="ignore"):
        mean = _nanmean(stack)
    for x, y in dead_now:
        mean[y, x] = math.nan
    diff = mean - baseline.mean_c
    valid = np.isfinite(diff)
    if not valid.any():
        raise DriftError("no pixel works in both the baseline and the new frames")
    shift = float(np.median(diff[valid]))
    worst = float(np.max(np.abs(diff[valid] - shift)))
    new_dead = tuple(sorted(dead_now - dead_then))
    recovered = tuple(sorted(dead_then - dead_now))
    drifted = abs(shift) > offset_tolerance_c or worst > pixel_tolerance_c
    if drifted and new_dead:
        verdict = DRIFT_AND_DEAD
    elif drifted:
        verdict = DRIFT
    elif new_dead:
        verdict = DEAD
    else:
        verdict = OK
    return DriftReport(verdict, shift, worst, new_dead, recovered, stack.shape[0])


def suggest_calibration(baseline: Baseline, frames: Any) -> dict[str, Any]:
    """A calibration (the format of ``--calibration``) that brings the new frames back to the baseline: the common shift as the offset,
    what is left of each pixel as its own offset and every dead pixel of the baseline and of the new frames as dead."""
    stack = _stack(frames)
    dead = sorted(set(find_dead_pixels(stack)) | set(baseline.dead_pixels))
    with np.errstate(invalid="ignore"):
        mean = _nanmean(stack)
    for x, y in dead:
        mean[y, x] = math.nan
    diff = baseline.mean_c - mean
    valid = np.isfinite(diff)
    if not valid.any():
        raise DriftError("no pixel works in both the baseline and the new frames")
    shift = float(np.median(diff[valid]))
    residual = np.where(valid, diff - shift, 0.0)
    return {"schema": 1, "gain": 1.0, "offset_c": round(shift, 4),
            "pixel_offsets_c": [[round(float(v), 4) for v in row] for row in residual], "dead_pixels": [list(p) for p in dead]}


def load_baseline(path: str | Path) -> Baseline:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise DriftError(f"cannot read the baseline: {error}") from error
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        raise DriftError(f"the baseline must be an object with schema {SCHEMA}")
    try:
        mean = np.array([[math.nan if v is None else float(v) for v in row] for row in data["mean_c"]], dtype=np.float64)
        width, height = int(data["width"]), int(data["height"])
        dead = tuple((int(p[0]), int(p[1])) for p in data["dead_pixels"])
        ambient = float(data["ambient_c"])
    except (KeyError, TypeError, ValueError, IndexError) as error:
        raise DriftError(f"the baseline is damaged: {error}") from error
    if mean.shape != (height, width):
        raise DriftError("the baseline size does not match its pixels")
    return Baseline(width, height, ambient, mean, dead)


def synthetic_reference(width: int, height: int, count: int = MIN_FRAMES, ambient_c: float = 24.0, seed: int = 7,
                        offset_c: float = 0.0, dead: tuple[tuple[int, int], ...] = ()) -> np.ndarray:
    """Frames of a uniform wall for tests and for trying the command without a sensor: ambient plus noise, an optional common offset
    and pixels that read NaN."""
    rng = np.random.default_rng(seed)
    stack = ambient_c + offset_c + rng.normal(0.0, 0.15, size=(count, height, width))
    for x, y in dead:
        stack[:, y, x] = math.nan
    return stack.astype(np.float32)
