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
usage: vision-companion [-h] {version,selftest,capture,analyze-roi,inspect,drift-check,rack-check,rack-watch,rack-simulate} ...

URTC-VISION-TOOL vision companion - thermal+RGB capture/processing pipeline.

positional arguments:
  {version,selftest,capture,analyze-roi,inspect,drift-check,rack-check,rack-watch,rack-simulate}
    version             Print the companion's version and exit.
    selftest            Run the full synthetic thermal+RGB pipeline end-to-end
                        and save its output (no hardware needed).
    capture             Read one calibrated thermal image from a URTC head
                        through a serial CAN adapter (SLCAN, 500 kbit/s) and
                        save it as .npy and false-colour PNG.
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

### `selftest [--out DIR] [--variant VARIANT] [--range LOW HIGH] [--calibration FILE]`

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
                                 [--range LOW HIGH] [--calibration FILE]

options:
  -h, --help            show this help message and exit
  --out OUT             Output directory for generated frames (default:
                        ./selftest_output)
  --variant {90640,90641,90642}
                        Thermal sensor variant: 90640 and 90642 are 32x24,
                        90641 is 16x12 (default: 90640)
  --range LOW HIGH      Fixed false-color scale in degrees C instead of the
                        frame's own min/max
  --calibration FILE    JSON file with a gain, an offset, per-pixel offsets
                        and dead pixels applied to the thermal frame
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

### `capture --port PORT [--bitrate KBPS] [--out DIR] [--variant VARIANT] [--range LOW HIGH] [--calibration FILE]`

Reads one calibrated thermal image from a URTC head that carries the thermal inspection tool, through a serial CAN adapter
(SLCAN, as the CANable and similar adapters speak it), and saves it the way `selftest` does: `thermal_frame.npy` and
`thermal_frame_falsecolor.png` in `--out` (default `./capture_output`). The `.npy` file is the one `inspect`, `drift-check` and
`rack-check` take with `--frame` or `--frames`.

`--port` is whatever pyserial can open: `COM3`, `/dev/ttyACM0` or a pyserial URL such as `socket://127.0.0.1:7777`. `--bitrate`
(kbit/s, default 500, the rate of a URTC bus) must be one of the SLCAN rates: 10, 20, 50, 100, 125, 250, 500, 800 or 1000. The
adapter is closed, set up, opened, used and closed again; the exchange is the one of `urtc_thermal.py`: `0x250` starts a capture,
`0x251` is polled until the head says it is ready, and each of the 48 chunks (12 for the 90641) is asked with `0x254` and answered
with four `0x255` frames. The `--range` and `--calibration` options are the ones of `selftest`.

Exit codes: `0` the image was read and saved; `1` the head did not deliver an image (it reported an error, never became ready or left a
chunk unanswered); `2` the adapter could not be opened or used (pyserial missing, a port that does not exist), or the arguments are wrong.
It has been run against a simulated adapter with a simulated head only: no real adapter, bus or head was used.

### `analyze-roi x0 y0 x1 y1 [--variant VARIANT] [--calibration FILE]`

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
                                    [--calibration FILE]
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
  --calibration FILE    JSON file with a gain, an offset, per-pixel offsets
                        and dead pixels applied to the thermal frame
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
                                    [--calibration FILE]
                                    x0 y0 x1 y1
vision-companion analyze-roi: error: argument x1: invalid int value: 'abc'
$ echo $?
2
```

### `inspect PLAN [--frame FILE] [--variant VARIANT] [--calibration FILE] [--out FILE] [--task NAME] [--source-id ID] [--timestamp-ms MS] [--export-jsonl FILE] [--opcua-nodes FILE] [--datalake URL] [--token-env NAME]`

Judges each component of a plan by the temperature rule of its kind: a joint that stayed cold after reflow, a part that runs too
hot. `PLAN` is a JSON file (`src/vision_companion/vision_companion/inspection.py` describes it): a `profile` with a rule per kind
of component (`expected_c` with `tolerance_c`, `min_c`, `max_c`, `min_rise_c`, `max_rise_c`; the rises are measured from the
ambient, which is the profile's `ambient_c` or the median of the frame) and the list of `components`, each with a `ref`, a `kind`,
a region `roi` in RGB pixels and optionally a `task`. The frame is a saved `.npy` (`--frame`) or the synthetic one. The verdict of
a component is `ok`, `cold`, `hot` or `no_data` (a region without thermal data is never ok); the overall result is `pass`, `fail` or
`incomplete`. It measures the temperature of the surface the camera sees, not of the junction inside a package.

`--out` writes the full report as JSON. The same measurements can be exported as a time series, per task: `--export-jsonl` (one
sample per line), `--opcua-nodes` (a map of node paths such as `URTC/Vision/<task>/<ref>/<statistic>` to values, for a gateway that
publishes OPC-UA; this tool runs no OPC-UA server) and `--datalake URL` (POST of each sample to the `/ingest` endpoint of the
HYDRA-UMC datalake, with the bearer token taken from the environment variable named by `--token-env`, never printed). A sample is
`{sourceId, kind, timestamp, fields}` with the fields `<ref>.min_c`, `.max_c`, `.mean_c` and `.p95_c`; `--timestamp-ms` defaults to now.

Exit codes: `0` pass, `1` incomplete (some region has no data), `2` bad plan or input or a failed export, `3` at least one component failed.

### `drift-check BASELINE [--frames FILE] [--variant VARIANT] [--update] [--ambient C] [--offset-tolerance C] [--pixel-tolerance C] [--suggest-calibration FILE]`

Checks the sensor against a reference scene: a wall at a stable temperature that fills the field of view. `--frames` is a `.npy` of
at least four frames, `(count, height, width)` (without it, synthetic frames). With `--update` the frames become the baseline
(`BASELINE`, a JSON file with the mean of every pixel, the ambient and the dead pixels); without it the frames are compared with the
baseline and the command reports the common offset shift, the worst pixel after removing it, the pixels that died and the ones that
work again. Dead pixels are those that never read a number, never change while the others do, read far from the level of the wall or
are too noisy. `--offset-tolerance` and `--pixel-tolerance` say what counts as drift. `--suggest-calibration FILE` writes a
calibration file (the format of `--calibration`) that brings the new frames back to the baseline.

Exit codes: `0` nothing found, `2` unreadable frames or baseline, `3` drift or dead pixels found.

### `rack-check STATE [--frame FILE] [--variant VARIANT] [--calibration FILE] [--ambient C] [--lang LANG] [--out FILE]`

Judges the tips of the tool rack from a thermal frame. `STATE` is a JSON file with `elapsed_ms` (the time since the targets were set) and, for each slot, its `slot` number, the `roi` where its tip is in the RGB image, `occupied` and `target_c`. The temperature of a slot is the hottest valid pixel of its region; the ambient is `--ambient` or the median of the frame. The verdict of a slot is `reached`, `heating`, `not_reached` (still short after a minute), `overshoot` (25 C above the target), `idle_ok` or `still_hot` (told to stay cold), `empty_ok` or `heater_in_empty_slot`, or `unknown` when the region has no reading. The rules are those of `slot_verify.c` of URTC-SMART-RACK and of the rack model of URTC-COMMON, and a shared set of cases checks the three; the limits are estimates for a soldering tip. The command only reports: it never sends anything to the rack. `--lang` chooses the language of the printed words (`en`, `es`, `de`, `fr`, `it`, `ja`, `zh`, `pt`); the verdicts in the JSON file stay the identifiers above.

Exit codes: `0` no fault, `2` unreadable state or frame, `3` at least one slot has a fault (`not_reached`, `overshoot`, `still_hot`, `heater_in_empty_slot`).

### `rack-watch STATE --frames FILE [--interval-ms N] [--variant VARIANT] [--calibration FILE] [--ambient C] [--lang LANG] [--out FILE]`

Closes the loop of the pre-heat. `--frames` is a stack of thermal frames `(n, height, width)` saved as `.npy`, one every `--interval-ms` (default 5000) from the moment the targets were set; `STATE` is the same file as for `rack-check` (its `elapsed_ms` is replaced by the position of each frame). Every frame is judged by the rules of `rack-check`, and for each slot the command prints the last verdict, when the target was first reached and whether a swap is allowed: `swap_ok` needs the last three readings all at the target (or all cold for a slot told to stay cold), `swap_wait` means the tip is not stable yet or has no reading, `swap_blocked` means the slot ends in a fault. The command only reports: it never sends anything to the rack.

Exit codes: `0` no slot ends in a fault, `2` unreadable state or frames, `3` at least one slot ends in a fault.

### `rack-simulate STATE --out FILE [--scenario NAME] [--count N] [--interval-ms N] [--variant VARIANT] [--seed N]`

Writes the frames a camera would give while a simulated rack heats, to try `rack-watch` without a camera or a rack. The tip of each occupied slot follows a first-order curve to its target. `--scenario` is `healthy` (default), `slow_heater` (the first heated slot misses the time allowed), `overshoot` (it ends 40 C above its target), `heater_in_empty_slot` (the first empty slot heats) or `dead_region` (the region of the first slot gives no reading). The same seed gives the same noise. The curves are estimates for a soldering tip, not measurements.

## Calibration file

`--calibration FILE` (on `selftest` and `analyze-roi`) applies a correction to
the thermal frame before it is rendered or measured. The file is JSON; only
`schema` is required, and any key that is not listed is an error so that a
misspelt key cannot leave a correction switched off.

```json
{
  "schema": 1,
  "gain": 1.02,
  "offset_c": -0.4,
  "pixel_offsets_c": [[0.0, 0.1, "... 32 numbers per row, 24 rows ..."]],
  "dead_pixels": [[5, 7], [12, 3]]
}
```

Each pixel becomes `pixel * gain + offset_c + pixel_offsets_c[y][x]`; `gain`
must be greater than 0. A dead pixel is set to NaN, so it is painted magenta and
counted as invalid in the statistics. A `pixel_offsets_c` map or a dead pixel
that does not fit the chosen `--variant` is reported as an error (exit `2`).
The code is in `src/vision_companion/vision_companion/calibration.py`.

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | ok |
| `1` | no thermal data: the requested region does not overlap the thermal field of view, or holds no valid pixel; `capture`: the head did not deliver an image |
| `3` | `inspect`: at least one component failed its rule; `drift-check`: drift or dead pixels were found; `rack-check`: a slot has a fault |
| `2` | invalid usage or input: a missing subcommand, a bad argument type or value, a degenerate region, an empty `--range`, a `--calibration` file that cannot be read or is not valid, `capture`: an adapter that cannot be opened |
