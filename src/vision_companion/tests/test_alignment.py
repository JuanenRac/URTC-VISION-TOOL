from __future__ import annotations

import numpy as np
import pytest

from alignment import AlignmentError, BoundingBox, analyze_rgb_roi, extract_roi_stats, rgb_roi_to_thermal_roi


def test_bounding_box_rejects_degenerate_box() -> None:
    with pytest.raises(ValueError):
        BoundingBox(10, 10, 10, 20)
    with pytest.raises(ValueError):
        BoundingBox(10, 10, 20, 10)


def test_rgb_roi_to_thermal_roi_scales_down() -> None:
    # Full RGB frame -> full thermal frame.
    roi = BoundingBox(0, 0, 640, 480)
    thermal_roi = rgb_roi_to_thermal_roi(roi, 640, 480, 32, 24)
    assert thermal_roi == BoundingBox(0, 0, 32, 24)


def test_rgb_roi_to_thermal_roi_center_box() -> None:
    # A 64x48-px RGB box centered on a 640x480 frame maps to a small
    # thermal box near the center of a 32x24 frame.
    roi = BoundingBox(288, 216, 352, 264)
    thermal_roi = rgb_roi_to_thermal_roi(roi, 640, 480, 32, 24)
    assert thermal_roi.x0 >= 13 and thermal_roi.x1 <= 19
    assert thermal_roi.y0 >= 10 and thermal_roi.y1 <= 14


def test_rgb_roi_to_thermal_roi_never_collapses_to_zero_size() -> None:
    # A single-pixel RGB box still yields a non-degenerate thermal box.
    roi = BoundingBox(0, 0, 1, 1)
    thermal_roi = rgb_roi_to_thermal_roi(roi, 640, 480, 32, 24)
    assert thermal_roi.x1 > thermal_roi.x0
    assert thermal_roi.y1 > thermal_roi.y0


def test_rgb_roi_to_thermal_roi_clamps_out_of_bounds_box() -> None:
    # An RGB box that runs past the frame edge still clamps into bounds.
    roi = BoundingBox(600, 460, 640, 480)
    thermal_roi = rgb_roi_to_thermal_roi(roi, 640, 480, 32, 24)
    assert 0 <= thermal_roi.x0 < thermal_roi.x1 <= 32
    assert 0 <= thermal_roi.y0 < thermal_roi.y1 <= 24


def test_rgb_roi_to_thermal_roi_rejects_non_positive_dimensions() -> None:
    roi = BoundingBox(0, 0, 10, 10)
    with pytest.raises(AlignmentError):
        rgb_roi_to_thermal_roi(roi, 0, 480, 32, 24)
    with pytest.raises(AlignmentError):
        rgb_roi_to_thermal_roi(roi, 640, 480, 32, -1)


def test_extract_roi_stats_matches_manual_numpy() -> None:
    frame = np.arange(24 * 32, dtype=np.float32).reshape(24, 32)
    roi = BoundingBox(2, 2, 6, 5)
    stats = extract_roi_stats(frame, roi)
    region = frame[2:5, 2:6]
    assert stats.min_c == pytest.approx(float(region.min()))
    assert stats.max_c == pytest.approx(float(region.max()))
    assert stats.mean_c == pytest.approx(float(region.mean()))
    assert stats.pixel_count == region.size


def test_extract_roi_stats_rejects_out_of_bounds_roi() -> None:
    frame = np.zeros((24, 32), dtype=np.float32)
    with pytest.raises(AlignmentError):
        extract_roi_stats(frame, BoundingBox(0, 0, 40, 10))
    with pytest.raises(AlignmentError):
        extract_roi_stats(frame, BoundingBox(-1, 0, 10, 10))


def test_analyze_rgb_roi_finds_hotspot_higher_than_corner() -> None:
    # A hot center + cool corners, like the real synthetic thermal frame's
    # soldering-tip-shaped hotspot - a center RGB ROI must read hotter than
    # a corner RGB ROI once mapped through to thermal space.
    frame = np.full((24, 32), 24.0, dtype=np.float32)
    frame[10:14, 14:18] = 80.0

    center_roi = BoundingBox(280, 210, 360, 270)
    corner_roi = BoundingBox(0, 0, 40, 40)

    center_stats = analyze_rgb_roi(frame, center_roi, rgb_width=640, rgb_height=480)
    corner_stats = analyze_rgb_roi(frame, corner_roi, rgb_width=640, rgb_height=480)

    assert center_stats.max_c > corner_stats.max_c
