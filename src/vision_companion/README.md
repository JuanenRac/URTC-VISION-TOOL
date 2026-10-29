# vision_companion

Host-side (CM5 / dev machine) companion for **URTC-VISION-TOOL**'s dual-modal
thermal (MLX9064x) + RGB tool head. Part of the [URTC-VISION-TOOL](../../README.md)
project - see the repo root README for the full project context.

There is no real PCB for this tool head yet (see [`../../hardware/README.md`](../../hardware/README.md)),
so no capture from a real sensor has happened. The companion speaks the CAN messages of URTC's thermal
inspection tool (`urtc_thermal.py`, identifiers `0x250`-`0x255`): it builds the requests and puts the
16-pixel chunks back together, `slcan_link.py` carries them over a serial CAN adapter (`capture`), and a
simulated adapter and head answer them in the tests. What's real and fully working today is the processing
pipeline those captures will feed: synthetic thermal/RGB frame generation, false-color thermal
rendering, real RGB->thermal ROI alignment and stats extraction (`alignment.py`; invalid pixels
are left out and counted), thermal sensors of 32x24 and 16x12 pixels, and stats reporting - runs
end-to-end with no hardware attached, verified by 183 real pytest cases.

## Layout

```text
src/vision_companion/
├── pyproject.toml            # packaging; the version is read from vision_companion/__init__.py
├── requirements.txt          # numpy + pillow
├── vision_companion/         # the importable package
│   ├── __init__.py           # __version__, defined once
│   ├── __main__.py           # python -m vision_companion
│   ├── cli.py                # the command line (version / selftest / capture / analyze-roi / inspect / drift-check / rack-check / rack-watch / rack-simulate)
│   ├── alignment.py          # ROI mapping and temperature statistics
│   ├── calibration.py        # the JSON thermal calibration (gain, offsets, dead pixels)
│   ├── urtc_thermal.py       # the CAN messages of URTC's thermal inspection tool (host side) and a simulated head
│   ├── slcan_link.py         # the serial CAN (SLCAN) adapter that carries them, used by `capture`
│   ├── inspection.py         # judges the components of a plan by temperature
│   ├── export.py             # JSON Lines, OPC UA node list and DataLake export of the readings
│   ├── sensor_drift.py       # drift of a sensor against a saved baseline
│   ├── rack_check.py         # per-slot verdict of the pre-heat of the tool rack
│   ├── rack_watch.py         # the same over a series of frames, with the swap decision
│   └── rack_text.py          # the words of the rack check in the eight languages
└── tests/                    # pytest
```

## Install & run

```bash
python3 -m venv .venv
# Linux/macOS:
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m vision_companion selftest

# Windows:
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m vision_companion selftest
```

Run these from `src/vision_companion/`. Or as an installed package (`pip install -e .` uses
`pyproject.toml`, which needs setuptools 77 or newer, and registers the `vision-companion`
console script):

```bash
pip install -e .
vision-companion version
vision-companion selftest --out ./selftest_output
```

`selftest` generates a synthetic MLX9064x-shaped thermal frame (32x24 by default, 16x12 with
`--variant 90641`, with a soldering-tip-like hotspot) and a synthetic RGB color-bar test pattern,
renders/saves both (`thermal_frame.npy`, `thermal_frame_falsecolor.png`, `rgb_frame.png`), and
prints their stats - proof the numpy/Pillow pipeline works end-to-end, independent of real
hardware. `--range LOW HIGH` fixes the false-color scale.

`analyze-roi X0 Y0 X1 Y1` maps an RGB-space bounding box (e.g. a component
detection from the Vision AI Node) into thermal-space, then reports real
min/max/mean/95th-percentile temperature for that region - the alignment path the README's
"Eye-in-Hand Alignment" feature describes, exercised end-to-end today
against the synthetic thermal frame:

```bash
vision-companion analyze-roi 280 210 360 270
```

Exit codes: `0` ok, `1` the region has no thermal data, `2` invalid usage or input (see
[`../../docs/CLI_REFERENCE.md`](../../docs/CLI_REFERENCE.md)).

## Tests

```bash
pip install -e ".[dev]"
pytest
ruff check .
```

183 real pytest cases: `tests/test_cli.py` (synthetic frame generation, false-color rendering,
CLI commands), `tests/test_alignment.py` (ROI coordinate mapping, out-of-bounds/degenerate-input
guards including a ROI with no real overlap with the thermal frame at all, ROI stats
extraction), `tests/test_robustness.py` (invalid pixels, sensor variants, degenerate input,
packaging), `tests/test_calibration.py` (the JSON thermal calibration), `tests/test_urtc_thermal.py` and `tests/test_slcan_link.py` (the thermal exchange and the serial adapter, against a simulated head), `tests/test_inspection.py`, `tests/test_rack_check.py` and `tests/test_rack_watch.py` (the inspection and the rack check) and `tests/test_docs.py` (the CLI reference matches the CLI).

See [`vision_companion/cli.py`](vision_companion/cli.py) and
[`vision_companion/alignment.py`](vision_companion/alignment.py) for the real, working code. `capture` reads
one image through a serial CAN adapter, but it has only been played against a simulated adapter and head;
a capture from a real MLX9064x or camera waits for hardware.
