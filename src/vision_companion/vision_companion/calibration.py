#!/usr/bin/env python3
# =============================================================================
# URTC-VISION-TOOL - vision_companion calibration module: calibration.py
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
# A thermal calibration read from a JSON file: one gain and one offset for the
# whole frame, an optional per-pixel offset map, and a list of dead pixels. The
# calibration is applied to a frame before any statistics are taken, so a
# bench-measured correction never has to be compiled into the program.
#
# File format (all keys optional except "schema"):
#
#   {
#     "schema": 1,
#     "gain": 1.0,                       # multiplies every pixel, must be > 0
#     "offset_c": 0.0,                   # added to every pixel after the gain
#     "pixel_offsets_c": [[0.0, ...]],   # height rows of width numbers
#     "dead_pixels": [[x, y], ...]       # become NaN, so statistics skip them
#   }
#
# Anything else in the file is an error: a misspelt key must not quietly leave
# a correction switched off.
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

SCHEMA = 1
_KNOWN_KEYS = {"schema", "gain", "offset_c", "pixel_offsets_c", "dead_pixels"}


class CalibrationError(ValueError):
    """The calibration file or data is not usable."""


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CalibrationError(f"{name} must be a number")
    if not math.isfinite(value):
        raise CalibrationError(f"{name} must be finite")
    return float(value)


@dataclass(frozen=True)
class Calibration:
    gain: float = 1.0
    offset_c: float = 0.0
    pixel_offsets_c: tuple[tuple[float, ...], ...] | None = None
    dead_pixels: tuple[tuple[int, int], ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.gain > 0.0 or not math.isfinite(self.gain):
            raise CalibrationError("gain must be a positive finite number")
        if not math.isfinite(self.offset_c):
            raise CalibrationError("offset_c must be finite")

    @property
    def is_identity(self) -> bool:
        return (self.gain == 1.0 and self.offset_c == 0.0
                and self.pixel_offsets_c is None and not self.dead_pixels)

    def apply(self, frame: np.ndarray) -> np.ndarray:
        """Return a corrected copy of a (height, width) frame; the input is
        never modified. Raises CalibrationError if the calibration was made
        for a frame of another size."""
        height, width = frame.shape
        out = frame.astype(np.float32) * np.float32(self.gain) + np.float32(self.offset_c)
        if self.pixel_offsets_c is not None:
            offsets = np.asarray(self.pixel_offsets_c, dtype=np.float32)
            if offsets.shape != (height, width):
                raise CalibrationError(
                    f"pixel_offsets_c is {offsets.shape[1]}x{offsets.shape[0]} "
                    f"but the frame is {width}x{height}")
            out = out + offsets
        for x, y in self.dead_pixels:
            if not (0 <= x < width and 0 <= y < height):
                raise CalibrationError(f"dead pixel ({x},{y}) is outside the {width}x{height} frame")
            out[y, x] = np.nan
        return out.astype(np.float32)


def calibration_from_dict(data: Any) -> Calibration:
    if not isinstance(data, dict):
        raise CalibrationError("the calibration must be a JSON object")
    unknown = set(data) - _KNOWN_KEYS
    if unknown:
        raise CalibrationError(f"unknown key(s): {', '.join(sorted(unknown))}")
    schema = data.get("schema")
    if isinstance(schema, bool) or schema != SCHEMA:
        raise CalibrationError(f"schema must be {SCHEMA}")

    gain = _number(data["gain"], "gain") if "gain" in data else 1.0
    offset = _number(data["offset_c"], "offset_c") if "offset_c" in data else 0.0

    offsets = None
    if "pixel_offsets_c" in data:
        rows = data["pixel_offsets_c"]
        if not isinstance(rows, list) or not rows or not all(isinstance(r, list) and r for r in rows):
            raise CalibrationError("pixel_offsets_c must be a non-empty list of non-empty rows")
        if len({len(r) for r in rows}) != 1:
            raise CalibrationError("pixel_offsets_c rows must all have the same length")
        offsets = tuple(
            tuple(_number(v, f"pixel_offsets_c[{y}][{x}]") for x, v in enumerate(row))
            for y, row in enumerate(rows))

    dead: list[tuple[int, int]] = []
    if "dead_pixels" in data:
        items = data["dead_pixels"]
        if not isinstance(items, list):
            raise CalibrationError("dead_pixels must be a list of [x, y] pairs")
        for item in items:
            if (not isinstance(item, list) or len(item) != 2
                    or not all(isinstance(v, int) and not isinstance(v, bool) and v >= 0 for v in item)):
                raise CalibrationError("each dead pixel must be [x, y] with two non-negative integers")
            dead.append((item[0], item[1]))
    return Calibration(gain=gain, offset_c=offset, pixel_offsets_c=offsets, dead_pixels=tuple(dead))


def load_calibration(path: str | Path) -> Calibration:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as error:
        raise CalibrationError(f"cannot read the calibration file: {error}") from error
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise CalibrationError(f"the calibration file is not valid JSON: {error}") from error
    return calibration_from_dict(data)
