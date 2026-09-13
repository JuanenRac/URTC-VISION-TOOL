#!/usr/bin/env python3
# =============================================================================
# URTC-VISION-TOOL - vision_companion alignment/ROI module: alignment.py
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0 - see LICENSE
# =============================================================================
# Real, hardware-independent logic for the README's "Eye-in-Hand Alignment"
# feature: mapping a region of interest between the RGB frame's resolution
# and the thermal sensor's much lower native resolution, then pulling real
# temperature statistics out of that region. There is no real dual-modal
# capture yet (no PCB - see main.py's own header comment), but once real
# RGB/thermal frames replace the synthetic generators, this module's inputs
# don't change shape, so nothing here has to be rewritten.
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class BoundingBox:
    """A pixel-space region of interest, upper-left origin, half-open
    (x1/y1 excluded) - the same convention most vision libraries use."""
    x0: int
    y0: int
    x1: int
    y1: int

    def __post_init__(self) -> None:
        if self.x1 <= self.x0 or self.y1 <= self.y0:
            raise ValueError(f"degenerate bounding box: {self!r}")


class AlignmentError(ValueError):
    pass


def rgb_roi_to_thermal_roi(
    roi: BoundingBox,
    rgb_width: int,
    rgb_height: int,
    thermal_width: int,
    thermal_height: int,
) -> BoundingBox | None:
    """Rescales a bounding box detected in RGB-frame pixel space into
    thermal-frame pixel space, assuming both sensors share the same field
    of view (a reasonable v0 assumption for a single rigid tool head - a
    real per-pixel homography needs an actual calibration pass against
    real hardware). A box that only partly overlaps the thermal frame is
    clamped to that overlap and widened by at least one thermal pixel in
    each axis so a small RGB detection (e.g. a single component) doesn't
    round away to a zero-size box.

    H043: a box that does not overlap the thermal frame AT ALL (e.g. a
    detection entirely to one side, or a stale/bogus RGB-space box) used
    to be clamped exactly the same way as a partially-overlapping one -
    silently landing on a 1-pixel-wide sliver at whichever thermal edge
    was nearest, so the caller got back a real-looking (if narrow)
    thermal reading for a region the thermal sensor never actually saw.
    That's returned as None here instead - "no data", not "the edge
    pixel's temperature" - so a caller can tell the two cases apart."""
    if rgb_width <= 0 or rgb_height <= 0 or thermal_width <= 0 or thermal_height <= 0:
        raise AlignmentError("frame dimensions must be positive")

    sx = thermal_width / rgb_width
    sy = thermal_height / rgb_height

    tx0 = int(np.floor(roi.x0 * sx))
    ty0 = int(np.floor(roi.y0 * sy))
    tx1 = int(np.ceil(roi.x1 * sx))
    ty1 = int(np.ceil(roi.y1 * sy))

    tx1 = max(tx1, tx0 + 1)
    ty1 = max(ty1, ty0 + 1)

    if tx1 <= 0 or tx0 >= thermal_width or ty1 <= 0 or ty0 >= thermal_height:
        return None  # no real intersection with the thermal frame at all

    tx0 = max(0, min(tx0, thermal_width - 1))
    ty0 = max(0, min(ty0, thermal_height - 1))
    tx1 = max(tx0 + 1, min(tx1, thermal_width))
    ty1 = max(ty0 + 1, min(ty1, thermal_height))

    return BoundingBox(tx0, ty0, tx1, ty1)


@dataclass(frozen=True)
class RoiStats:
    min_c: float
    max_c: float
    mean_c: float
    pixel_count: int

    @property
    def is_empty(self) -> bool:
        """True for H043's "no real data" result - a requested ROI that
        does not overlap the thermal frame at all. `min_c`/`max_c`/`mean_c`
        are NaN in that case (never a real temperature reading with
        pixel_count == 0 sitting behind it), so a caller checking this
        property first can't accidentally treat NaN as a real value."""
        return self.pixel_count == 0

    @staticmethod
    def empty() -> "RoiStats":
        return RoiStats(min_c=math.nan, max_c=math.nan, mean_c=math.nan, pixel_count=0)


def extract_roi_stats(thermal_frame: np.ndarray, roi: BoundingBox) -> RoiStats:
    """Pulls real min/max/mean temperature out of a region of the thermal
    frame - the actual "does this component run hot" answer the README's
    thermal-inspection use case needs, once fed a real MLX9064x frame
    instead of the synthetic one."""
    height, width = thermal_frame.shape
    if roi.x0 < 0 or roi.y0 < 0 or roi.x1 > width or roi.y1 > height:
        raise AlignmentError(f"roi {roi!r} is out of bounds for a {width}x{height} frame")

    region = thermal_frame[roi.y0:roi.y1, roi.x0:roi.x1]
    return RoiStats(
        min_c=float(region.min()),
        max_c=float(region.max()),
        mean_c=float(region.mean()),
        pixel_count=int(region.size),
    )


def analyze_rgb_roi(
    thermal_frame: np.ndarray,
    rgb_roi: BoundingBox,
    rgb_width: int,
    rgb_height: int,
) -> RoiStats:
    """Convenience wrapper: given a bounding box detected in RGB space (e.g.
    from a component-detection model upstream), maps it into thermal space
    and returns real temperature stats for that exact region - the
    end-to-end path the README's Eye-in-Hand Alignment feature describes.

    H043: when `rgb_roi` doesn't overlap the thermal frame at all, this
    returns `RoiStats.empty()` (`is_empty` True, `pixel_count == 0`) rather
    than ever calling `extract_roi_stats()` against a clamped edge sliver -
    see `rgb_roi_to_thermal_roi()`'s own note on why that used to read as a
    real, if narrow, temperature."""
    thermal_height, thermal_width = thermal_frame.shape
    thermal_roi = rgb_roi_to_thermal_roi(rgb_roi, rgb_width, rgb_height, thermal_width, thermal_height)
    if thermal_roi is None:
        return RoiStats.empty()
    return extract_roi_stats(thermal_frame, thermal_roi)
