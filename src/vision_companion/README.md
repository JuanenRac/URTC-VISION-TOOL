# vision_companion

Host-side (CM5 / dev machine) companion for **URTC-VISION-TOOL**'s dual-modal
thermal (MLX9064x) + RGB tool head. Part of the [URTC-VISION-TOOL](../../README.md)
project - see the repo root README for the full project context.

There is no real PCB for this tool head yet (see [`../../hardware/README.md`](../../hardware/README.md)),
so real sensor capture isn't implemented. The companion has no bus access of its own, but it speaks the
CAN messages of URTC's thermal inspection tool (`urtc_thermal.py`, identifiers `0x250`-`0x255`): it builds
the requests and puts the 16-pixel chunks back together, and a simulated head answers them in the tests. What's real and fully working today is the processing
pipeline those captures will feed: synthetic thermal/RGB frame generation, false-color thermal
rendering, real RGB->thermal ROI alignment and stats extraction (`alignment.py`; invalid pixels
are left out and counted), thermal sensors of 32x24 and 16x12 pixels, and stats reporting - runs
end-to-end with no hardware attached, verified by 135 real pytest cases.

## Layout

```text
src/vision_companion/
├── pyproject.toml            # packaging; the version is read from vision_companion/__init__.py
├── requirements.txt          # numpy + pillow
├── vision_companion/         # the importable package
│   ├── __init__.py           # __version__, defined once
│   ├── __main__.py           # python -m vision_companion
│   ├── cli.py                # the command line (version / selftest / analyze-roi)
│   ├── alignment.py          # ROI mapping and temperature statistics
│   └── urtc_thermal.py       # the CAN messages of URTC's thermal inspection tool (host side) and a simulated head
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

135 real pytest cases: `tests/test_cli.py` (synthetic frame generation, false-color rendering,
CLI commands), `tests/test_alignment.py` (ROI coordinate mapping, out-of-bounds/degenerate-input
guards including a ROI with no real overlap with the thermal frame at all, ROI stats
extraction), `tests/test_robustness.py` (invalid pixels, sensor variants, degenerate input,
packaging), `tests/test_calibration.py` (the JSON thermal calibration) and `tests/test_docs.py` (the CLI reference matches the CLI).

See [`vision_companion/cli.py`](vision_companion/cli.py) and
[`vision_companion/alignment.py`](vision_companion/alignment.py) for the real, working code. A real
MLX9064x/camera capture step will be added once hardware exists.
