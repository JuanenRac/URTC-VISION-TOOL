# URTC-VISION-TOOL — vision_companion CLI Reference

`vision-companion` (`src/vision_companion/vision_companion/cli.py`, installed as a
console script via `src/vision_companion/pyproject.toml`, or run directly
as `python -m vision_companion` from `src/vision_companion/`) is the host-side
(CM5/dev-machine, not the STM32 — see `src/main.c`) companion for
URTC-VISION-TOOL's thermal+RGB tool head. There is no real MLX9064x/RGB camera
wired up yet (no PCB exists), so this CLI's `selftest` and `analyze-roi` run
entirely against a synthetic thermal frame (a deterministic, seeded
soldering-tip-shaped hotspot) and a synthetic RGB test pattern — real, working
code end-to-end, just fed synthetic frames until real dual-modal capture
exists. The examples below come from real runs of the installed CLI (file paths
shortened); the test `src/vision_companion/tests/test_docs.py` checks that this
page names the current version, every command and every option, and the exit
codes.

## Usage

```
$ vision-companion -h
usage: vision-companion [-h] {version,selftest,analyze-roi} ...

URTC-VISION-TOOL vision companion - thermal+RGB capture/processing pipeline.

positional arguments:
  {version,selftest,analyze-roi}
    version             Print the companion's version and exit.
    selftest            Run the full synthetic thermal+RGB pipeline end-to-end
                        and save its output (no hardware needed).
    analyze-roi         Map an RGB-space bounding box to thermal space and
                        report real temperature stats for it (runs against a
                        synthetic thermal frame - no hardware needed).

options:
  -h, --help            show this help message and exit
```

A subcommand is required — running `vision-companion` with no arguments
prints this same usage to stderr and exits `2` (argparse's own
`required=True` on the subparsers).

## Commands

### `version`

The version is defined once, in `vision_companion/__init__.py`; the package
metadata reads it from there.

```
$ vision-companion version
vision-companion v0.0.3 (URTC-VISION-TOOL)
```

### `selftest [--out DIR] [--variant VARIANT] [--range LOW HIGH]`

Runs the full synthetic pipeline end-to-end — generates a thermal frame (32x24
for the default MLX90640, the real native resolution) and a 640x480 RGB
test-bar frame, renders both, and saves all three artifacts. This is the honest
"does this actually work" check for the project — it exercises every real code
path with no hardware attached.

`--variant` selects the thermal sensor variant: `90640` and `90642` are 32x24,
`90641` is 16x12 (default `90640`). `--range LOW HIGH` fixes the false-color
scale in degrees C, so that two renderings can be compared by color; without it
the scale follows the frame's own finite minimum and maximum and is never
narrower than 1 degree, so a uniform frame is drawn in a mid color instead of
as the coldest pixel. Pixels without a valid temperature (NaN, infinity) are
painted magenta. `HIGH` must be greater than `LOW`, otherwise the command
prints an error and exits `2`.

```
$ vision-companion selftest -h
usage: vision-companion selftest [-h] [--out OUT]
                                 [--variant {90640,90641,90642}]
                                 [--range LOW HIGH]

options:
  -h, --help            show this help message and exit
  --out OUT             Output directory for generated frames (default:
                        ./selftest_output)
  --variant {90640,90641,90642}
                        Thermal sensor variant: 90640 and 90642 are 32x24,
                        90641 is 16x12 (default: 90640)
  --range LOW HIGH      Fixed false-color scale in degrees C instead of the
                        frame's own min/max
```

```
$ vision-companion selftest --out /tmp/vc_selftest_out
vision-companion selftest v0.0.3
  thermal frame: 32x24 min=26.46C max=78.97C mean=47.79C
    -> /tmp/vc_selftest_out/thermal_frame.npy
    -> /tmp/vc_selftest_out/thermal_frame_falsecolor.png
  rgb frame:     640x480
    -> /tmp/vc_selftest_out/rgb_frame.png
selftest OK - synthetic pipeline ran end-to-end (no hardware attached).
```

The thermal stats are real and reproducible run-to-run — the synthetic
generator seeds its noise RNG (`np.random.default_rng(seed=42)`), so the
same min/max/mean prints every time. `--out` really is created
(`mkdir(parents=True, exist_ok=True)`) and really does contain a raw
`.npy` temperature array, a false-color-rendered PNG (a hand-rolled
black→blue→red→yellow→white ramp, nearest-neighbor upscaled 16x), and
the RGB test-pattern PNG:

```
$ ls -la /tmp/vc_selftest_out
-rw-r--r-- 1 juane 197609 1962 rgb_frame.png
-rw-r--r-- 1 juane 197609 3200 thermal_frame.npy
-rw-r--r-- 1 juane 197609 3846 thermal_frame_falsecolor.png
```

### `analyze-roi x0 y0 x1 y1 [--variant VARIANT]`

Maps an RGB-space bounding box (e.g. a component detection from an
upstream vision model) into thermal-sensor space and reports real
min/max/mean/95th-percentile temperature + pixel count for that region,
against the same synthetic thermal frame `selftest` uses. This exercises
`alignment.py`'s real ROI-rescaling and stats-extraction logic end-to-end — the
same code path a real detection would drive once real dual-modal capture exists.
Pixels without a valid temperature are left out of the statistics and reported
on their own line. The 95th percentile is a hot-spot figure that a single
spurious hot pixel cannot move the way it moves the maximum.

```
$ vision-companion analyze-roi -h
usage: vision-companion analyze-roi [-h] [--variant {90640,90641,90642}]
                                    x0 y0 x1 y1

positional arguments:
  x0                    ROI left edge, in RGB pixels (0-640)
  y0                    ROI top edge, in RGB pixels (0-480)
  x1                    ROI right edge, in RGB pixels (0-640)
  y1                    ROI bottom edge, in RGB pixels (0-480)

options:
  -h, --help            show this help message and exit
  --variant {90640,90641,90642}
                        Thermal sensor variant: 90640 and 90642 are 32x24,
                        90641 is 16x12 (default: 90640)
```

```
$ vision-companion analyze-roi 100 100 300 300
RGB ROI (100,100)-(300,300) in a 640x480 frame
  -> thermal stats: min=38.44C max=77.39C mean=58.75C p95=75.31C (100 thermal px)
$ echo $?
0
```

**No data** — a box that does not overlap the thermal field of view at all is
reported as "no data", never as the temperature of whichever edge pixel is
nearest. This is a result, not an error, and exits `1`:

```
$ vision-companion analyze-roi 700 0 760 60
RGB ROI (700,0)-(760,60) in a 640x480 frame
  -> no thermal data: this RGB ROI does not overlap the thermal sensor's field of view
$ echo $?
1
```

**Partly outside the frame** — a box that reaches past the RGB frame is measured
on the part that lies inside it, with a warning on stderr; the exit code stays
`0`:

```
$ vision-companion analyze-roi -50 0 100 100
warning: the ROI reaches outside the 640x480 RGB frame; only the part inside it is measured
RGB ROI (-50,0)-(100,100) in a 640x480 frame
  -> thermal stats: min=26.46C max=34.93C mean=29.64C p95=33.28C (25 thermal px)
```

**Error path 1** — a degenerate box (`x1 <= x0` or `y1 <= y0`) is rejected with a
one-line message on stderr and exit code `2`, the same code as a usage error:

```
$ vision-companion analyze-roi 300 300 100 100
error: degenerate bounding box: BoundingBox(x0=300, y0=300, x1=100, y1=100)
$ echo $?
2
```

**Error path 2** — a non-integer coordinate is caught by argparse
itself before `analyze-roi` ever runs, with the usual argparse usage
message on stderr and exit code `2`:

```
$ vision-companion analyze-roi 0 0 abc 100
usage: vision-companion analyze-roi [-h] [--variant {90640,90641,90642}]
                                    x0 y0 x1 y1
vision-companion analyze-roi: error: argument x1: invalid int value: 'abc'
$ echo $?
2
```

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | ok |
| `1` | no thermal data: the requested region does not overlap the thermal field of view, or holds no valid pixel |
| `2` | invalid usage or input: a missing subcommand, a bad argument type or value, a degenerate region, an empty `--range` |
