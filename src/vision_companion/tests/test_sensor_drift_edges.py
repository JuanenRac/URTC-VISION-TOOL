# =============================================================================
# URTC-VISION-TOOL - vision_companion tests: test_sensor_drift_edges.py
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""The refusals and the edges of the check of the sensor: wrong shapes, too few frames, nothing that works,
a baseline that is unreadable or damaged. Fixed seeds."""
from __future__ import annotations

import json
import math

import numpy as np
import pytest

from vision_companion import sensor_drift as sd

W, H = 8, 6


def frames(count: int = 6, seed: int = 3, **kwargs) -> np.ndarray:
    return sd.synthetic_reference(W, H, count, seed=seed, **kwargs)


def test_the_frames_must_be_two_or_three_dimensional():
    with pytest.raises(sd.DriftError, match="height, width"):
        sd.make_baseline(np.zeros((2, 3, 4, 5)))
    with pytest.raises(sd.DriftError, match="height, width"):
        sd.make_baseline(np.zeros(10))


def test_too_few_frames_are_refused_with_the_number_that_is_needed():
    with pytest.raises(sd.DriftError, match=f"at least {sd.MIN_FRAMES}"):
        sd.make_baseline(frames(sd.MIN_FRAMES - 1))
    with pytest.raises(sd.DriftError, match=f"at least {sd.MIN_FRAMES}"):
        sd.make_baseline(np.zeros((H, W)))            # one frame of two dimensions counts as one


def test_a_sensor_that_reads_no_number_at_all_has_no_baseline():
    with pytest.raises(sd.DriftError, match="every pixel is dead"):
        sd.make_baseline(np.full((sd.MIN_FRAMES, H, W), math.nan))


def test_the_ambient_temperature_can_be_given_and_otherwise_is_the_median_of_the_working_pixels():
    stack = frames(ambient_c=30.0)
    assert sd.make_baseline(stack, ambient_c=21.5).ambient_c == 21.5
    assert abs(sd.make_baseline(stack).ambient_c - 30.0) < 0.2


def test_frames_of_another_size_cannot_be_compared_with_the_baseline():
    base = sd.make_baseline(frames())
    with pytest.raises(sd.DriftError, match="but the baseline is"):
        sd.compare(base, sd.synthetic_reference(W + 1, H, 6))


def test_when_no_pixel_works_in_both_nothing_can_be_compared_or_suggested():
    base = sd.make_baseline(frames())
    dead_now = np.full((sd.MIN_FRAMES, H, W), math.nan)
    with pytest.raises(sd.DriftError, match="no pixel works"):
        sd.compare(base, dead_now)
    with pytest.raises(sd.DriftError, match="no pixel works"):
        sd.suggest_calibration(base, dead_now)


def test_a_new_dead_pixel_and_a_recovered_one_are_reported_with_their_positions():
    base = sd.make_baseline(frames(dead=((1, 1),)))
    report = sd.compare(base, frames(seed=4, dead=((2, 3),)))
    assert report.new_dead_pixels == ((2, 3),) and report.recovered_pixels == ((1, 1),)
    assert report.verdict == sd.DEAD and report.frames == 6


def test_a_common_shift_of_the_whole_sensor_is_a_drift_whose_size_is_measured():
    base = sd.make_baseline(frames())
    report = sd.compare(base, frames(seed=5, offset_c=1.2))
    assert report.verdict == sd.DRIFT and abs(report.offset_shift_c - 1.2) < 0.25
    assert sd.compare(base, frames(seed=5, offset_c=0.0)).verdict == sd.OK


def test_the_suggested_calibration_has_the_format_of_the_calibration_file_and_lists_every_dead_pixel():
    base = sd.make_baseline(frames(dead=((0, 0),)))
    suggestion = sd.suggest_calibration(base, frames(seed=6, offset_c=-0.8, dead=((3, 2),)))
    assert suggestion["schema"] == 1 and suggestion["gain"] == 1.0
    assert abs(suggestion["offset_c"] - 0.8) < 0.25
    assert sorted(suggestion["dead_pixels"]) == [[0, 0], [3, 2]]
    assert len(suggestion["pixel_offsets_c"]) == H and all(len(row) == W for row in suggestion["pixel_offsets_c"])


def test_a_baseline_that_is_written_and_read_again_is_the_same(tmp_path):
    base = sd.make_baseline(frames(dead=((2, 2),)))
    path = tmp_path / "baseline.json"
    document = {
        "schema": sd.SCHEMA, "width": W, "height": H, "ambient_c": base.ambient_c,
        "mean_c": [[None if math.isnan(v) else float(v) for v in row] for row in base.mean_c],
        "dead_pixels": [list(p) for p in base.dead_pixels],
    }
    path.write_text(json.dumps(document), encoding="utf-8")
    again = sd.load_baseline(path)
    assert (again.width, again.height, again.dead_pixels) == (W, H, ((2, 2),))
    assert np.allclose(again.mean_c, base.mean_c, equal_nan=True)


@pytest.mark.parametrize("content, message", [
    (None, "cannot read the baseline"),
    ("{oops", "cannot read the baseline"),
    ("[1, 2]", "schema"),
    ('{"schema": 99}', "schema"),
    ('{"schema": 1}', "damaged"),
    ('{"schema": 1, "width": "x", "height": 1, "ambient_c": 1, "mean_c": [[1]], "dead_pixels": []}', "damaged"),
    ('{"schema": 1, "width": 2, "height": 2, "ambient_c": 1, "mean_c": [[1]], "dead_pixels": []}', "does not match"),
])
def test_a_baseline_that_cannot_be_used_is_refused_with_the_reason(tmp_path, content, message):
    path = tmp_path / "baseline.json"
    if content is not None:
        path.write_text(content, encoding="utf-8")
    with pytest.raises(sd.DriftError, match=message):
        sd.load_baseline(path)
