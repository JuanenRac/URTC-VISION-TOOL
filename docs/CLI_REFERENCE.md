# URTC-VISION-TOOL — vision_companion CLI Reference

`vision-companion` (`src/vision_companion/main.py`, installed as a
console script via `src/vision_companion/pyproject.toml`, or run directly
as `python main.py`) is the host-side (CM5/dev-machine, not the STM32 —
see `main.c`) companion for URTC-VISION-TOOL's thermal+RGB tool head.
There is no real MLX9064x/RGB camera wired up yet (no PCB exists), so
this CLI's `selftest` and `analyze-roi` run entirely against a synthetic
thermal frame (a deterministic, seeded soldering-tip-shaped hotspot) and
a synthetic RGB test pattern — real, working code end-to-end, just fed
synthetic frames until real dual-modal capture exists. Every example
below was captured from a real run of the installed CLI — not written
from memory.

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

```
$ vision-companion version
vision-companion v0.0.1 (URTC-VISION-TOOL)
```

### `selftest [--out DIR]`

Runs the full synthetic pipeline end-to-end — generates a 32x24 thermal
frame (`THERMAL_WIDTH`/`THERMAL_HEIGHT`, the real MLX90640 native
resolution) and a 640x480 RGB test-bar frame, renders both, and saves
all three artifacts. This is the honest "does this actually work" check
for the project — it exercises every real code path with no hardware
attached.

```
$ vision-companion selftest -h
usage: vision-companion selftest [-h] [--out OUT]

options:
  -h, --help  show this help message and exit
  --out OUT   Output directory for generated frames (default:
              ./selftest_output)
```

```
$ vision-companion selftest --out /tmp/vc_selftest_out
vision-companion selftest v0.0.1
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

### `analyze-roi x0 y0 x1 y1`

Maps an RGB-space bounding box (e.g. a component detection from an
upstream vision model) into thermal-sensor space and reports real
min/max/mean temperature + pixel count for that region, against the same
synthetic thermal frame `selftest` uses. This exercises `alignment.py`'s
real ROI-rescaling and stats-extraction logic end-to-end — the same code
path a real detection would drive once real dual-modal capture exists.

```
$ vision-companion analyze-roi -h
usage: vision-companion analyze-roi [-h] x0 y0 x1 y1

positional arguments:
  x0          ROI left edge, in RGB pixels (0-640)
  y0          ROI top edge, in RGB pixels (0-480)
  x1          ROI right edge, in RGB pixels (0-640)
  y1          ROI bottom edge, in RGB pixels (0-480)

options:
  -h, --help  show this help message and exit
```

```
$ vision-companion analyze-roi 100 100 300 300
RGB ROI (100,100)-(300,300) in a 640x480 frame
  -> thermal stats: min=38.44C max=77.39C mean=58.75C (100 thermal px)
```

**Real error path 1** — a degenerate box (`x1 <= x0` or `y1 <= y0`) is
rejected by `BoundingBox.__post_init__` in `alignment.py`. This raises
an uncaught `ValueError`, so the CLI exits `1` with a real Python
traceback rather than a friendly message — an honest reflection of the
code today, not a designed UX:

```
$ vision-companion analyze-roi 300 300 100 100
Traceback (most recent call last):
  File ".../main.py", line 211, in <module>
    sys.exit(main())
  File ".../main.py", line 207, in main
    return args.func(args)
  File ".../main.py", line 162, in cmd_analyze_roi
    roi = BoundingBox(args.x0, args.y0, args.x1, args.y1)
  File ".../alignment.py", line 32, in __post_init__
    raise ValueError(f"degenerate bounding box: {self!r}")
ValueError: degenerate bounding box: BoundingBox(x0=300, y0=300, x1=100, y1=100)
$ echo $?
1
```

**Real error path 2** — a non-integer coordinate is caught by argparse
itself before `analyze-roi` ever runs, with the usual argparse usage
message on stderr and exit code `2`:

```
$ vision-companion analyze-roi 0 0 abc 100
usage: vision-companion analyze-roi [-h] x0 y0 x1 y1
vision-companion analyze-roi: error: argument x1: invalid int value: 'abc'
$ echo $?
2
```

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | ok |
| `1` | an unhandled exception from real domain logic (e.g. a degenerate ROI) |
| `2` | argparse usage error (missing subcommand, bad argument type) |

There is no dedicated exit-code contract beyond argparse's own
conventions and Python's default "uncaught exception -> 1" — this table
documents the real, observed behavior above, not a designed scheme.
