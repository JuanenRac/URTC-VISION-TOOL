"""Edge cases of the companion: invalid pixels, degenerate input, sensor
variants and the packaging contract."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from vision_companion import __version__, cli
from vision_companion.alignment import BoundingBox, analyze_rgb_roi, extract_roi_stats

PACKAGE_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------- statistics

def test_a_nan_pixel_does_not_turn_the_statistics_into_nan() -> None:
    frame = np.full((24, 32), 24.0, dtype=np.float32)
    frame[3, 3] = np.nan
    stats = extract_roi_stats(frame, BoundingBox(0, 0, 8, 8))
    assert stats.min_c == pytest.approx(24.0)
    assert stats.max_c == pytest.approx(24.0)
    assert stats.mean_c == pytest.approx(24.0)
    assert stats.pixel_count == 63
    assert stats.invalid_pixel_count == 1
    assert not stats.is_empty


def test_infinite_pixels_are_left_out_too() -> None:
    frame = np.full((24, 32), 30.0, dtype=np.float32)
    frame[0, 0] = np.inf
    frame[0, 1] = -np.inf
    stats = extract_roi_stats(frame, BoundingBox(0, 0, 4, 4))
    assert stats.max_c == pytest.approx(30.0)
    assert stats.invalid_pixel_count == 2
    assert stats.pixel_count == 14


def test_a_region_of_invalid_pixels_is_empty_not_a_reading() -> None:
    frame = np.full((24, 32), np.nan, dtype=np.float32)
    stats = extract_roi_stats(frame, BoundingBox(0, 0, 4, 4))
    assert stats.is_empty
    assert stats.pixel_count == 0
    assert stats.invalid_pixel_count == 16
    assert np.isnan(stats.max_c)


def test_the_95th_percentile_ignores_one_spurious_hot_pixel() -> None:
    frame = np.full((24, 32), 25.0, dtype=np.float32)
    frame[2, 2] = 400.0
    stats = extract_roi_stats(frame, BoundingBox(0, 0, 8, 8))
    assert stats.max_c == pytest.approx(400.0)
    assert stats.p95_c == pytest.approx(25.0)


def test_a_sixteen_by_twelve_sensor_maps_the_full_frame_onto_itself() -> None:
    frame = np.arange(12 * 16, dtype=np.float32).reshape(12, 16)
    stats = analyze_rgb_roi(frame, BoundingBox(0, 0, 640, 480), rgb_width=640, rgb_height=480)
    assert stats.pixel_count == 12 * 16
    assert stats.min_c == pytest.approx(0.0)
    assert stats.max_c == pytest.approx(float(12 * 16 - 1))


# ------------------------------------------------------------------ rendering

def test_a_uniform_frame_is_not_painted_as_the_coldest_pixel() -> None:
    frame = np.full((4, 4), 30.0, dtype=np.float32)
    pixels = np.asarray(cli.thermal_to_false_color(frame))
    assert int(pixels.sum()) > 0
    assert len({tuple(p) for p in pixels.reshape(-1, 3)}) == 1


def test_invalid_pixels_are_painted_in_the_marker_color() -> None:
    frame = np.array([[10.0, np.nan], [20.0, 30.0]], dtype=np.float32)
    pixels = np.asarray(cli.thermal_to_false_color(frame))
    assert tuple(pixels[4, 20]) == cli.INVALID_PIXEL_COLOR  # the NaN pixel, 16x upscale
    assert tuple(pixels[4, 4]) != cli.INVALID_PIXEL_COLOR


def test_a_frame_with_no_valid_pixel_renders_without_error() -> None:
    frame = np.full((3, 3), np.nan, dtype=np.float32)
    image = cli.thermal_to_false_color(frame)
    assert isinstance(image, Image.Image)
    assert set(map(tuple, np.asarray(image).reshape(-1, 3))) == {cli.INVALID_PIXEL_COLOR}


def test_a_fixed_range_makes_two_frames_comparable() -> None:
    cool = np.full((2, 2), 30.0, dtype=np.float32)
    hot = np.full((2, 2), 70.0, dtype=np.float32)
    cool_pixel = np.asarray(cli.thermal_to_false_color(cool, (20.0, 80.0)))[0, 0]
    hot_pixel = np.asarray(cli.thermal_to_false_color(hot, (20.0, 80.0)))[0, 0]
    assert tuple(cool_pixel) != tuple(hot_pixel)
    with pytest.raises(ValueError):
        cli.thermal_to_false_color(cool, (50.0, 50.0))


# ------------------------------------------------------------------------ CLI

def test_a_degenerate_roi_is_a_clean_error_not_a_traceback(capsys: pytest.CaptureFixture[str]) -> None:
    code = cli.main(["analyze-roi", "300", "300", "100", "100"])
    captured = capsys.readouterr()
    assert code == cli.EXIT_BAD_INPUT == 2
    assert "degenerate bounding box" in captured.err
    assert "Traceback" not in captured.err + captured.out


def test_a_roi_reaching_outside_the_frame_is_measured_with_a_warning(capsys: pytest.CaptureFixture[str]) -> None:
    code = cli.main(["analyze-roi", "-50", "0", "100", "100"])
    captured = capsys.readouterr()
    assert code == 0
    assert "outside" in captured.err
    assert "thermal stats" in captured.out


def test_a_roi_inside_the_frame_prints_no_warning(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["analyze-roi", "100", "100", "300", "300"]) == 0
    assert capsys.readouterr().err == ""


def test_analyze_roi_prints_the_95th_percentile(capsys: pytest.CaptureFixture[str]) -> None:
    cli.main(["analyze-roi", "0", "0", "640", "480"])
    assert "p95=" in capsys.readouterr().out


def test_selftest_supports_the_sixteen_by_twelve_variant(tmp_path: Path) -> None:
    assert cli.main(["selftest", "--variant", "90641", "--out", str(tmp_path)]) == 0
    assert np.load(tmp_path / "thermal_frame.npy").shape == (12, 16)
    assert cli.main(["selftest", "--variant", "90642", "--out", str(tmp_path)]) == 0
    assert np.load(tmp_path / "thermal_frame.npy").shape == (24, 32)


def test_selftest_accepts_a_fixed_range_and_refuses_an_empty_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["selftest", "--range", "20", "80", "--out", str(tmp_path)]) == 0
    assert cli.main(["selftest", "--range", "50", "50", "--out", str(tmp_path)]) == cli.EXIT_BAD_INPUT
    assert "--range" in capsys.readouterr().err


def test_an_unknown_variant_is_a_usage_error() -> None:
    with pytest.raises(SystemExit) as raised:
        cli.build_parser().parse_args(["selftest", "--variant", "12345"])
    assert raised.value.code == 2


# ------------------------------------------------------------------ packaging

def test_the_module_runs_with_python_dash_m() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "vision_companion", "version"],
        cwd=PACKAGE_ROOT, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0
    assert f"v{__version__}" in result.stdout


def test_the_version_has_a_single_source() -> None:
    pyproject = (PACKAGE_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'dynamic = ["version"]' in pyproject
    assert 'attr = "vision_companion.__version__"' in pyproject
    assert "\nversion = \"" not in pyproject.replace("version = { attr", "")
    assert "setuptools>=77" in pyproject


def test_no_top_level_module_named_main_or_alignment_is_installed() -> None:
    pyproject = (PACKAGE_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "py-modules" not in pyproject
    assert 'packages = ["vision_companion"]' in pyproject
    assert not (PACKAGE_ROOT / "main.py").exists()
    assert not (PACKAGE_ROOT / "alignment.py").exists()
