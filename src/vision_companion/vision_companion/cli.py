#!/usr/bin/env python3
# =============================================================================
# URTC-VISION-TOOL - vision_companion command line: cli.py
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
# Host-side (CM5 / dev machine, NOT the STM32 - see ../../src/main.c's own
# header comment) companion for URTC-VISION-TOOL's dual-modal thermal+RGB tool
# head. There is no real MLX9064x/RGB camera wired up yet (no PCB exists -
# see ../../hardware/README.md), so `capture` (reading the real sensors over
# I2C/USB) isn't implemented here yet. What IS real and fully working today is
# the processing pipeline those captures will feed: synthetic-frame
# generation, false-color thermal rendering, and stats reporting - this
# runs end-to-end with no hardware attached, and the real capture step only has to
# swap `generate_synthetic_thermal_frame()`/`generate_synthetic_rgb_frame()`
# for a real sensor read, everything downstream already works.
#
# Exit codes: 0 ok, 1 the region has no thermal data, 2 invalid usage or input
# (argparse errors and a degenerate region share this code).
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from . import __version__
from . import export as export_module
from . import inspection, rack_check, sensor_drift
from .alignment import BoundingBox, analyze_rgb_roi
from .calibration import Calibration, CalibrationError, load_calibration

EXIT_OK = 0
EXIT_NO_DATA = 1
EXIT_BAD_INPUT = 2
EXIT_FINDINGS = 3   # the inspection failed, or the sensor check found drift or dead pixels

# Thermal sensor variants of the MLX9064x family and their native resolution
# (width, height). The default is the MLX90640, the one this tool head targets.
THERMAL_VARIANTS: dict[str, tuple[int, int]] = {
    "90640": (32, 24),
    "90641": (16, 12),
    "90642": (32, 24),
}
DEFAULT_VARIANT = "90640"

# Native resolution of the default sensor - kept as the synthetic frame's shape
# too, so code written against these frames doesn't need to change once real
# sensor reads replace the synthetic generator.
THERMAL_WIDTH, THERMAL_HEIGHT = THERMAL_VARIANTS[DEFAULT_VARIANT]

# A modest, common machine-vision resolution - no real RGB camera is
# confirmed for this board yet, so this is a placeholder frame size, not a
# spec commitment (see README.md's own hardware status note).
RGB_WIDTH = 640
RGB_HEIGHT = 480

# The false-color scale never gets narrower than this many degrees: a frame
# that is (almost) uniform would otherwise be stretched into noise or collapse
# to a single black color indistinguishable from "the coldest pixel".
MIN_FALSE_COLOR_SPAN_C = 1.0
# Pixels without a valid temperature (NaN, infinity) are painted in this color.
INVALID_PIXEL_COLOR = (255, 0, 255)


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


def thermal_to_false_color(
    frame: np.ndarray,
    value_range: tuple[float, float] | None = None,
) -> Image.Image:
    """Map a temperature frame to a black -> blue -> red -> yellow -> white
    false-color image (a small hand-rolled "ironbow"-style ramp - no
    matplotlib dependency needed for 4 lerp segments).

    By default the scale follows this frame's own finite min/max, widened to at
    least ``MIN_FALSE_COLOR_SPAN_C`` degrees around the middle of the data, so a
    uniform frame is drawn in a mid color and not as "the coldest pixel". With
    ``value_range=(low, high)`` the scale is fixed, so two frames can be compared
    by color. Pixels that are not finite are painted in ``INVALID_PIXEL_COLOR``
    instead of dragging the whole image to black."""
    finite = np.isfinite(frame)
    if value_range is not None:
        lo, hi = float(value_range[0]), float(value_range[1])
        if not hi > lo:
            raise ValueError(f"value range must have high > low, got {value_range!r}")
    elif finite.any():
        lo, hi = float(frame[finite].min()), float(frame[finite].max())
        if hi - lo < MIN_FALSE_COLOR_SPAN_C:
            middle = (hi + lo) / 2.0
            lo, hi = middle - MIN_FALSE_COLOR_SPAN_C / 2.0, middle + MIN_FALSE_COLOR_SPAN_C / 2.0
    else:
        lo, hi = 0.0, MIN_FALSE_COLOR_SPAN_C  # nothing to scale: every pixel is invalid anyway
    safe = np.where(finite, frame, lo)
    norm = np.clip((safe - lo) / (hi - lo), 0.0, 1.0)

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
    rgb[~finite] = INVALID_PIXEL_COLOR
    # Thermal sensors are low-resolution by nature (32x24 here) - nearest-
    # neighbor upscale keeps the real per-pixel readings visually distinct
    # instead of a smooth blur implying precision the sensor doesn't have.
    image = Image.fromarray(rgb, mode="RGB")
    return image.resize((width * 16, height * 16), resample=Image.Resampling.NEAREST)


def cmd_version(_args: argparse.Namespace) -> int:
    print(f"vision-companion v{__version__} (URTC-VISION-TOOL)")
    return EXIT_OK


def _variant_shape(args: argparse.Namespace) -> tuple[int, int]:
    return THERMAL_VARIANTS[getattr(args, "variant", DEFAULT_VARIANT)]


def _load_cal(args: argparse.Namespace) -> Calibration | None:
    path = getattr(args, "calibration", None)
    return load_calibration(path) if path else None


def cmd_selftest(args: argparse.Namespace) -> int:
    """Runs the full synthetic pipeline end-to-end - generates a thermal
    frame + an RGB frame, renders/saves both, and prints stats. Exercises
    every real code path in this module without needing any hardware, so
    it's the honest "does this actually work" check for this project."""
    value_range = tuple(args.range) if getattr(args, "range", None) else None
    if value_range is not None and not value_range[1] > value_range[0]:
        print(f"error: --range needs HIGH greater than LOW, got {value_range[0]} {value_range[1]}", file=sys.stderr)
        return EXIT_BAD_INPUT

    try:
        calibration = _load_cal(args)
    except CalibrationError as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_BAD_INPUT

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    width, height = _variant_shape(args)
    thermal = generate_synthetic_thermal_frame(width, height)
    if calibration is not None:
        try:
            thermal = calibration.apply(thermal)
        except CalibrationError as error:
            print(f"error: {error}", file=sys.stderr)
            return EXIT_BAD_INPUT
    rgb = generate_synthetic_rgb_frame()

    thermal_npy_path = out_dir / "thermal_frame.npy"
    thermal_png_path = out_dir / "thermal_frame_falsecolor.png"
    rgb_png_path = out_dir / "rgb_frame.png"

    np.save(thermal_npy_path, thermal)
    thermal_to_false_color(thermal, value_range).save(thermal_png_path)
    Image.fromarray(rgb, mode="RGB").save(rgb_png_path)

    print(f"vision-companion selftest v{__version__}")
    print(f"  thermal frame: {thermal.shape[1]}x{thermal.shape[0]} "
          f"min={thermal.min():.2f}C max={thermal.max():.2f}C mean={thermal.mean():.2f}C")
    print(f"    -> {thermal_npy_path}")
    print(f"    -> {thermal_png_path}")
    print(f"  rgb frame:     {rgb.shape[1]}x{rgb.shape[0]}")
    print(f"    -> {rgb_png_path}")
    print("selftest OK - synthetic pipeline ran end-to-end (no hardware attached).")
    return EXIT_OK


def cmd_analyze_roi(args: argparse.Namespace) -> int:
    """Runs the real RGB->thermal ROI alignment + stats pipeline against a
    synthetic thermal frame - the same code path a real detection (e.g. a
    component bounding box from the Vision AI Node) would drive once real
    dual-modal capture exists. Exercises alignment.py end-to-end today."""
    try:
        roi = BoundingBox(args.x0, args.y0, args.x1, args.y1)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_BAD_INPUT
    if roi.x0 < 0 or roi.y0 < 0 or roi.x1 > RGB_WIDTH or roi.y1 > RGB_HEIGHT:
        print(f"warning: the ROI reaches outside the {RGB_WIDTH}x{RGB_HEIGHT} RGB frame; "
              "only the part inside it is measured", file=sys.stderr)

    width, height = _variant_shape(args)
    thermal = generate_synthetic_thermal_frame(width, height)
    try:
        calibration = _load_cal(args)
        if calibration is not None:
            thermal = calibration.apply(thermal)
    except CalibrationError as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_BAD_INPUT
    stats = analyze_rgb_roi(thermal, roi, rgb_width=RGB_WIDTH, rgb_height=RGB_HEIGHT)

    print(f"RGB ROI ({roi.x0},{roi.y0})-({roi.x1},{roi.y1}) in a {RGB_WIDTH}x{RGB_HEIGHT} frame")
    if stats.is_empty:
        # this ROI does not overlap the thermal sensor's field of
        # view at all (or holds no valid pixel) - honestly report "no data",
        # never a min/max/mean computed from whatever pixel happened to sit
        # at the nearest thermal edge.
        print("  -> no thermal data: this RGB ROI does not overlap the thermal sensor's field of view")
        return EXIT_NO_DATA
    print(f"  -> thermal stats: min={stats.min_c:.2f}C max={stats.max_c:.2f}C "
          f"mean={stats.mean_c:.2f}C p95={stats.p95_c:.2f}C ({stats.pixel_count} thermal px)")
    if stats.invalid_pixel_count:
        print(f"  -> {stats.invalid_pixel_count} invalid thermal px left out of the statistics")
    return EXIT_OK


def _load_frames(path: str | None, variant_shape: tuple[int, int], count: int = 1) -> np.ndarray:
    """A saved frame (or a stack of frames) from a .npy file, or the synthetic frame when no file is given."""
    if path:
        try:
            return np.load(path)
        except (OSError, ValueError) as error:
            raise CalibrationError(f"cannot read the frames: {error}") from error
    width, height = variant_shape
    return generate_synthetic_thermal_frame(width, height)


def cmd_inspect(args: argparse.Namespace) -> int:
    """Judge every component of a plan by the temperature rule of its kind, from a saved frame or the synthetic one."""
    import json
    import time
    try:
        plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
        profile, components = inspection.plan_from_dict(plan)
        thermal = _load_frames(args.frame, _variant_shape(args))
        if thermal.ndim != 2:
            raise CalibrationError("--frame must hold one (height, width) frame")
        calibration = _load_cal(args)
        if calibration is not None:
            thermal = calibration.apply(thermal)
    except (OSError, ValueError, CalibrationError) as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_BAD_INPUT
    report = inspection.inspect(thermal, components, profile, RGB_WIDTH, RGB_HEIGHT)
    document = inspection.report_to_dict(report)
    print(f"inspection '{report.profile}': {report.overall} (ambient {report.ambient_c:.1f}C)")
    for result in report.results:
        print(f"  {result.ref} ({result.kind}): {result.verdict}" + (" - " + "; ".join(result.reasons) if result.reasons else ""))
    if args.out:
        Path(args.out).write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
        print(f"  -> {args.out}")
    samples = export_module.samples_from_report(report, args.timestamp_ms or int(time.time() * 1000), args.source_id, args.task)
    try:
        if args.export_jsonl:
            Path(args.export_jsonl).write_text(export_module.to_jsonl(samples), encoding="utf-8")
            print(f"  -> {args.export_jsonl} ({len(samples)} sample(s))")
        if args.opcua_nodes:
            Path(args.opcua_nodes).write_text(json.dumps(export_module.opcua_nodes(samples), indent=2) + "\n", encoding="utf-8")
            print(f"  -> {args.opcua_nodes}")
        if args.datalake:
            accepted = export_module.post_samples(args.datalake, samples, args.token_env)
            print(f"  -> datalake accepted {accepted} sample(s)")
    except export_module.ExportError as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_BAD_INPUT
    if report.overall == inspection.FAIL:
        return EXIT_FINDINGS
    return EXIT_NO_DATA if report.overall == inspection.INCOMPLETE else EXIT_OK


def cmd_drift_check(args: argparse.Namespace) -> int:
    """Compare frames of the reference scene with a stored baseline (or store the baseline with --update)."""
    import json
    try:
        frames = np.load(args.frames) if args.frames else sensor_drift.synthetic_reference(*_variant_shape(args))
        if args.update:
            baseline = sensor_drift.make_baseline(frames, args.ambient)
            Path(args.baseline).write_text(json.dumps(baseline.to_dict()) + "\n", encoding="utf-8")
            print(f"baseline written to {args.baseline}: {baseline.width}x{baseline.height}, ambient {baseline.ambient_c:.2f}C, {len(baseline.dead_pixels)} dead pixel(s)")
            return EXIT_OK
        baseline = sensor_drift.load_baseline(args.baseline)
        report = sensor_drift.compare(baseline, frames, args.offset_tolerance, args.pixel_tolerance)
        if args.suggest_calibration:
            Path(args.suggest_calibration).write_text(json.dumps(sensor_drift.suggest_calibration(baseline, frames), indent=2) + "\n", encoding="utf-8")
            print(f"  -> calibration suggested in {args.suggest_calibration}")
    except (OSError, ValueError, sensor_drift.DriftError) as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_BAD_INPUT
    print(f"sensor check: {report.verdict} ({report.frames} frame(s))")
    print(f"  common offset shift {report.offset_shift_c:+.2f}C, worst pixel {report.worst_pixel_shift_c:.2f}C after removing it")
    if report.new_dead_pixels:
        print("  new dead pixels: " + ", ".join(f"({x},{y})" for x, y in report.new_dead_pixels))
    if report.recovered_pixels:
        print("  pixels working again: " + ", ".join(f"({x},{y})" for x, y in report.recovered_pixels))
    return EXIT_OK if report.verdict == sensor_drift.OK else EXIT_FINDINGS


def cmd_rack_check(args: argparse.Namespace) -> int:
    """Judge the tips of the tool rack by the temperature a thermal frame shows in each slot (see rack_check.py)."""
    import json
    try:
        state = rack_check.load_state(args.state)
        thermal = _load_frames(args.frame, _variant_shape(args))
        if thermal.ndim != 2:
            raise CalibrationError("--frame must hold one (height, width) frame")
        calibration = _load_cal(args)
        if calibration is not None:
            thermal = calibration.apply(thermal)
        results = rack_check.check_rack(thermal, state, RGB_WIDTH, RGB_HEIGHT, args.ambient)
    except (OSError, ValueError, CalibrationError, rack_check.RackCheckError) as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_BAD_INPUT
    for r in results:
        shown = "no reading" if r.measured_c is None else f"{r.measured_c:.1f}C"
        print(f"slot {r.slot}: {'occupied' if r.occupied else 'empty'}, ordered {r.commanded_c}C, read {shown}: {r.verdict}" + (" FAULT" if r.is_fault else ""))
    if args.out:
        Path(args.out).write_text(json.dumps(rack_check.results_to_dict(results, args.ambient), indent=2) + "\n", encoding="utf-8")
        print(f"  -> {args.out}")
    return EXIT_FINDINGS if any(r.is_fault for r in results) else EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vision-companion",
        description="URTC-VISION-TOOL vision companion - thermal+RGB capture/processing pipeline.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("version", help="Print the companion's version and exit.").set_defaults(func=cmd_version)

    variant_help = "Thermal sensor variant: 90640 and 90642 are 32x24, 90641 is 16x12 (default: %(default)s)"

    calibration_help = (
        "JSON file with a gain, an offset, per-pixel offsets and dead pixels "
        "applied to the thermal frame"
    )

    selftest = subparsers.add_parser(
        "selftest",
        help="Run the full synthetic thermal+RGB pipeline end-to-end and save its output (no hardware needed).",
    )
    selftest.add_argument(
        "--out", default="selftest_output",
        help="Output directory for generated frames (default: ./selftest_output)",
    )
    selftest.add_argument("--variant", choices=sorted(THERMAL_VARIANTS), default=DEFAULT_VARIANT, help=variant_help)
    selftest.add_argument(
        "--range", nargs=2, type=float, metavar=("LOW", "HIGH"),
        help="Fixed false-color scale in degrees C instead of the frame's own min/max",
    )
    selftest.add_argument("--calibration", metavar="FILE", help=calibration_help)
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
    analyze_roi.add_argument("--variant", choices=sorted(THERMAL_VARIANTS), default=DEFAULT_VARIANT, help=variant_help)
    analyze_roi.add_argument("--calibration", metavar="FILE", help=calibration_help)
    analyze_roi.set_defaults(func=cmd_analyze_roi)

    inspect_cmd = subparsers.add_parser(
        "inspect",
        help="Judge each component of a plan (regions found in the RGB image) by the temperature rule of its kind: cold joints, "
             "parts that run hot. Optionally export the min/max/mean of every region as a time series.",
    )
    inspect_cmd.add_argument("plan", help="JSON plan: a profile of rules and the list of components with their regions")
    inspect_cmd.add_argument("--frame", metavar="FILE", help="a thermal frame saved as .npy (default: the synthetic frame)")
    inspect_cmd.add_argument("--variant", choices=sorted(THERMAL_VARIANTS), default=DEFAULT_VARIANT, help=variant_help)
    inspect_cmd.add_argument("--calibration", metavar="FILE", help=calibration_help)
    inspect_cmd.add_argument("--out", metavar="FILE", help="write the full report as JSON")
    inspect_cmd.add_argument("--task", default="", help="name of the run, for the components that have no task of their own")
    inspect_cmd.add_argument("--source-id", default=export_module.DEFAULT_SOURCE, help="source id of the exported samples (default: %(default)s)")
    inspect_cmd.add_argument("--timestamp-ms", type=int, default=0, help="Unix time in milliseconds of the samples (default: now)")
    inspect_cmd.add_argument("--export-jsonl", metavar="FILE", help="write the samples, one JSON object per line")
    inspect_cmd.add_argument("--opcua-nodes", metavar="FILE", help="write a map of OPC-UA node paths to values")
    inspect_cmd.add_argument("--datalake", metavar="URL", help="POST the samples to the HYDRA-UMC datalake at this address")
    inspect_cmd.add_argument("--token-env", default="HYDRA_UMC_DATALAKE_INGEST_TOKEN", help="environment variable that holds the datalake token (default: %(default)s)")
    inspect_cmd.set_defaults(func=cmd_inspect)

    drift_cmd = subparsers.add_parser(
        "drift-check",
        help="Compare frames of a reference scene (a uniform wall) with a stored baseline: dead pixels and offset drift.",
    )
    drift_cmd.add_argument("baseline", help="the baseline JSON file")
    drift_cmd.add_argument("--frames", metavar="FILE", help="at least 4 frames of the reference scene as .npy, (count, height, width) (default: synthetic frames)")
    drift_cmd.add_argument("--variant", choices=sorted(THERMAL_VARIANTS), default=DEFAULT_VARIANT, help=variant_help)
    drift_cmd.add_argument("--update", action="store_true", help="store these frames as the new baseline instead of comparing")
    drift_cmd.add_argument("--ambient", type=float, default=None, help="room temperature in C when the baseline is stored (default: the median of the frames)")
    drift_cmd.add_argument("--offset-tolerance", type=float, default=0.5, metavar="C", help="common shift that counts as drift (default: %(default)s)")
    drift_cmd.add_argument("--pixel-tolerance", type=float, default=1.0, metavar="C", help="shift of one pixel, beyond the common one, that counts as drift (default: %(default)s)")
    drift_cmd.add_argument("--suggest-calibration", metavar="FILE", help="write a calibration file that brings the new frames back to the baseline")
    drift_cmd.set_defaults(func=cmd_drift_check)

    rack_cmd = subparsers.add_parser(
        "rack-check",
        help="Judge the tips of the tool rack from a thermal frame: reached, too slow, too hot, a heater on in an empty slot.",
    )
    rack_cmd.add_argument("state", help="JSON state of the rack: elapsed_ms and, for each slot, its region in the RGB image, occupied and target_c")
    rack_cmd.add_argument("--frame", metavar="FILE", help="a thermal frame saved as .npy (default: the synthetic frame)")
    rack_cmd.add_argument("--variant", choices=sorted(THERMAL_VARIANTS), default=DEFAULT_VARIANT, help=variant_help)
    rack_cmd.add_argument("--calibration", metavar="FILE", help=calibration_help)
    rack_cmd.add_argument("--ambient", type=float, default=None, help="room temperature in C (default: the median of the frame)")
    rack_cmd.add_argument("--out", metavar="FILE", help="write the verdicts as JSON")
    rack_cmd.set_defaults(func=cmd_rack_check)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
