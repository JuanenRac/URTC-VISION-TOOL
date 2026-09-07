from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

import main


def test_generate_synthetic_thermal_frame_shape_and_range() -> None:
    frame = main.generate_synthetic_thermal_frame()
    assert frame.shape == (main.THERMAL_HEIGHT, main.THERMAL_WIDTH)
    assert frame.dtype == np.float32
    # Ambient ~24C baseline, hotspot up to ~55C above it - real, plausible
    # soldering-tip-shaped numbers, not zeros.
    assert 15.0 < frame.min() < 30.0
    assert frame.max() > 50.0


def test_generate_synthetic_thermal_frame_hotspot_is_centered() -> None:
    frame = main.generate_synthetic_thermal_frame()
    center = frame[main.THERMAL_HEIGHT // 2, main.THERMAL_WIDTH // 2]
    corner = frame[0, 0]
    assert center > corner


def test_generate_synthetic_thermal_frame_is_deterministic() -> None:
    # selftest's output has to be reproducible - the RNG is seeded.
    frame_a = main.generate_synthetic_thermal_frame()
    frame_b = main.generate_synthetic_thermal_frame()
    assert np.array_equal(frame_a, frame_b)


def test_generate_synthetic_rgb_frame_shape_and_bar_colors() -> None:
    frame = main.generate_synthetic_rgb_frame()
    assert frame.shape == (main.RGB_HEIGHT, main.RGB_WIDTH, 3)
    assert frame.dtype == np.uint8
    # First bar is white, last bar is black - the classic SMPTE-style ramp.
    assert tuple(frame[0, 0]) == (255, 255, 255)
    assert tuple(frame[0, -1]) == (0, 0, 0)


def test_generate_synthetic_rgb_frame_custom_size() -> None:
    frame = main.generate_synthetic_rgb_frame(width=80, height=60)
    assert frame.shape == (60, 80, 3)


def test_thermal_to_false_color_returns_upscaled_rgb_image() -> None:
    frame = main.generate_synthetic_thermal_frame()
    image = main.thermal_to_false_color(frame)
    assert isinstance(image, Image.Image)
    assert image.mode == "RGB"
    assert image.size == (main.THERMAL_WIDTH * 16, main.THERMAL_HEIGHT * 16)


def test_thermal_to_false_color_coldest_pixel_is_dark_hottest_is_bright() -> None:
    frame = np.array([[0.0, 50.0], [100.0, 25.0]], dtype=np.float32)
    image = main.thermal_to_false_color(frame)
    pixels = np.asarray(image)
    # Nearest-neighbor 16x upscale: sample well inside each source pixel's
    # footprint so we land on the pixel we expect, not a neighbor.
    coldest = pixels[4, 4]
    hottest = pixels[20, 20]
    assert int(coldest.sum()) < int(hottest.sum())


def test_thermal_to_false_color_handles_flat_frame() -> None:
    # min == max: division-by-zero guard must hold, not crash or NaN out.
    frame = np.full((4, 4), 30.0, dtype=np.float32)
    image = main.thermal_to_false_color(frame)
    pixels = np.asarray(image)
    assert not np.isnan(pixels).any()


def test_cmd_version_prints_version(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main.cmd_version(argparse_namespace())
    captured = capsys.readouterr()
    assert exit_code == 0
    assert main.__version__ in captured.out


def test_cmd_selftest_writes_real_output_files(tmp_path) -> None:
    args = main.build_parser().parse_args(["selftest", "--out", str(tmp_path)])
    exit_code = args.func(args)
    assert exit_code == 0
    assert (tmp_path / "thermal_frame.npy").exists()
    assert (tmp_path / "thermal_frame_falsecolor.png").exists()
    assert (tmp_path / "rgb_frame.png").exists()


def test_cmd_analyze_roi_reports_stats(capsys: pytest.CaptureFixture[str]) -> None:
    args = main.build_parser().parse_args(["analyze-roi", "0", "0", "640", "480"])
    exit_code = args.func(args)
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "thermal stats" in captured.out


def test_build_parser_requires_a_command() -> None:
    parser = main.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])


def argparse_namespace():
    import argparse
    return argparse.Namespace()
