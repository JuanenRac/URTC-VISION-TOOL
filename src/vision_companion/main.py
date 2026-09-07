#!/usr/bin/env python3
# =============================================================================
# URTC-VISION-TOOL - vision_companion entry point: main.py
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0 - see LICENSE
# =============================================================================
# Host-side (CM5 / dev machine, NOT the STM32 - see ../main.c's own header
# comment) companion for URTC-VISION-TOOL's dual-modal thermal+RGB tool
# head. There is no real MLX9064x/RGB camera wired up yet (no PCB exists -
# see ../../hardware/), so `capture` (reading the real sensors over I2C/
# USB) isn't implemented here yet. What IS real and fully working today is
# the processing pipeline those captures will feed: synthetic-frame
# generation, false-color thermal rendering, and stats reporting - this
# runs end-to-end with no hardware attached, and the real capture step only has to
# swap `generate_synthetic_thermal_frame()`/`generate_synthetic_rgb_frame()`
# for a real sensor read, everything downstream already works.
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from alignment import BoundingBox, analyze_rgb_roi

__version__ = "0.0.1"

# Native resolution of the MLX90640 thermal sensor family this tool head
# targets (see README.md) - kept as the synthetic frame's shape too, so
# code written against these frames doesn't need to change once real
# sensor reads replace the synthetic generator.
THERMAL_WIDTH = 32
THERMAL_HEIGHT = 24

# A modest, common machine-vision resolution - no real RGB camera is
# confirmed for this board yet, so this is a placeholder frame size, not a
# spec commitment (see README.md's own hardware status note).
RGB_WIDTH = 640
RGB_HEIGHT = 480


def generate_synthetic_thermal_frame(width: int = THERMAL_WIDTH, height: int = THERMAL_HEIGHT) -> np.ndarray:
    """Produce a synthetic MLX9064x-shaped temperature frame (degrees C)
    with a smooth radial hotspot plus sensor-like noise - stands in for a
    real I2C read from the sensor (no hardware exists yet, see this
    module's own header comment). Realistic enough to exercise the
    false-color rendering and stats pipeline below with real numbers,
    not zeros."""
    yy, xx = np.mgrid[0:height, 0:width]
    cx, cy = width / 2.0, height / 2.0
    # Ambient ~24C baseline with a ~55C radial hotspot in the middle,
    # loosely modeling a soldering-tip-shaped thermal signature - this
    # tool head's actual use case (see README.md's Key Features).
    dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    hotspot = 55.0 * np.exp(-(dist ** 2) / (2 * (width / 4.0) ** 2))
    ambient = 24.0
    rng = np.random.default_rng(seed=42)  # deterministic - selftest output is reproducible
    noise = rng.normal(loc=0.0, scale=0.15, size=(height, width))
    return (ambient + hotspot + noise).astype(np.float32)


def generate_synthetic_rgb_frame(width: int = RGB_WIDTH, height: int = RGB_HEIGHT) -> np.ndarray:
    """Produce a synthetic RGB test pattern (vertical color bars, the same
    calibration pattern broadcast engineers have used for decades) -
    stands in for a real camera capture (no hardware exists yet). Gives
    the rendering/alignment pipeline real, structured pixel data to work
    with instead of a blank frame."""
    bars = [
        (255, 255, 255), (255, 255, 0), (0, 255, 255), (0, 255, 0),
        (255, 0, 255), (255, 0, 0), (0, 0, 255), (0, 0, 0),
    ]
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    bar_width = width // len(bars)
    for i, color in enumerate(bars):
        x0 = i * bar_width
        x1 = width if i == len(bars) - 1 else (i + 1) * bar_width
        frame[:, x0:x1] = color
    return frame


def thermal_to_false_color(frame: np.ndarray) -> Image.Image:
    """Map a temperature frame to a black -> blue -> red -> yellow -> white
    false-color image (a small hand-rolled "ironbow"-style ramp - no
    matplotlib dependency needed for 4 lerp segments), normalized to this
    frame's own min/max so a real sensor's actual dynamic range always
    renders usefully instead of clipping against fixed bounds."""
    lo, hi = float(frame.min()), float(frame.max())
    span = hi - lo if hi > lo else 1.0
    norm = np.clip((frame - lo) / span, 0.0, 1.0)

    stops = np.array([
        (0.0, (0, 0, 0)),
        (0.33, (0, 0, 255)),
        (0.66, (255, 0, 0)),
        (0.85, (255, 255, 0)),
        (1.0, (255, 255, 255)),
    ], dtype=object)

    height, width = norm.shape
    rgb = np.zeros((height, width, 3), dtype=np.uint8)
    for i in range(len(stops) - 1):
        t0, c0 = stops[i]
        t1, c1 = stops[i + 1]
        mask = (norm >= t0) & (norm <= t1)
        local_t = np.where(t1 > t0, (norm - t0) / (t1 - t0), 0.0)
        for channel in range(3):
            rgb[..., channel] = np.where(
                mask,
                (c0[channel] + (c1[channel] - c0[channel]) * local_t).astype(np.uint8),
                rgb[..., channel],
            )
    # Thermal sensors are low-resolution by nature (32x24 here) - nearest-
    # neighbor upscale keeps the real per-pixel readings visually distinct
    # instead of a smooth blur implying precision the sensor doesn't have.
    image = Image.fromarray(rgb, mode="RGB")
    return image.resize((width * 16, height * 16), resample=Image.NEAREST)


def cmd_version(_args: argparse.Namespace) -> int:
    print(f"vision-companion v{__version__} (URTC-VISION-TOOL)")
    return 0


def cmd_selftest(args: argparse.Namespace) -> int:
    """Runs the full synthetic pipeline end-to-end - generates a thermal
    frame + an RGB frame, renders/saves both, and prints stats. Exercises
    every real code path in this module without needing any hardware, so
    it's the honest "does this actually work" check for this project."""
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    thermal = generate_synthetic_thermal_frame()
    rgb = generate_synthetic_rgb_frame()

    thermal_npy_path = out_dir / "thermal_frame.npy"
    thermal_png_path = out_dir / "thermal_frame_falsecolor.png"
    rgb_png_path = out_dir / "rgb_frame.png"

    np.save(thermal_npy_path, thermal)
    thermal_to_false_color(thermal).save(thermal_png_path)
    Image.fromarray(rgb, mode="RGB").save(rgb_png_path)

    print(f"vision-companion selftest v{__version__}")
    print(f"  thermal frame: {thermal.shape[1]}x{thermal.shape[0]} "
          f"min={thermal.min():.2f}C max={thermal.max():.2f}C mean={thermal.mean():.2f}C")
    print(f"    -> {thermal_npy_path}")
    print(f"    -> {thermal_png_path}")
    print(f"  rgb frame:     {rgb.shape[1]}x{rgb.shape[0]}")
    print(f"    -> {rgb_png_path}")
    print("selftest OK - synthetic pipeline ran end-to-end (no hardware attached).")
    return 0


def cmd_analyze_roi(args: argparse.Namespace) -> int:
    """Runs the real RGB->thermal ROI alignment + stats pipeline against a
    synthetic thermal frame - the same code path a real detection (e.g. a
    component bounding box from the Vision AI Node) would drive once real
    dual-modal capture exists. Exercises alignment.py end-to-end today."""
    thermal = generate_synthetic_thermal_frame()
    roi = BoundingBox(args.x0, args.y0, args.x1, args.y1)
    stats = analyze_rgb_roi(thermal, roi, rgb_width=RGB_WIDTH, rgb_height=RGB_HEIGHT)

    print(f"RGB ROI ({roi.x0},{roi.y0})-({roi.x1},{roi.y1}) in a {RGB_WIDTH}x{RGB_HEIGHT} frame")
    print(f"  -> thermal stats: min={stats.min_c:.2f}C max={stats.max_c:.2f}C "
          f"mean={stats.mean_c:.2f}C ({stats.pixel_count} thermal px)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vision-companion",
        description="URTC-VISION-TOOL vision companion - thermal+RGB capture/processing pipeline.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("version", help="Print the companion's version and exit.").set_defaults(func=cmd_version)

    selftest = subparsers.add_parser(
        "selftest",
        help="Run the full synthetic thermal+RGB pipeline end-to-end and save its output (no hardware needed).",
    )
    selftest.add_argument(
        "--out", default="selftest_output",
        help="Output directory for generated frames (default: ./selftest_output)",
    )
    selftest.set_defaults(func=cmd_selftest)

    analyze_roi = subparsers.add_parser(
        "analyze-roi",
        help="Map an RGB-space bounding box to thermal space and report real temperature stats for it "
             "(runs against a synthetic thermal frame - no hardware needed).",
    )
    analyze_roi.add_argument("x0", type=int, help=f"ROI left edge, in RGB pixels (0-{RGB_WIDTH})")
    analyze_roi.add_argument("y0", type=int, help=f"ROI top edge, in RGB pixels (0-{RGB_HEIGHT})")
    analyze_roi.add_argument("x1", type=int, help=f"ROI right edge, in RGB pixels (0-{RGB_WIDTH})")
    analyze_roi.add_argument("y1", type=int, help=f"ROI bottom edge, in RGB pixels (0-{RGB_HEIGHT})")
    analyze_roi.set_defaults(func=cmd_analyze_roi)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
