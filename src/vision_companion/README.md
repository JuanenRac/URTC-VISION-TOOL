# vision_companion

Host-side (CM5 / dev machine) companion for **URTC-VISION-TOOL**'s dual-modal
thermal (MLX9064x) + RGB tool head. Part of the [URTC-VISION-TOOL](../../README.md)
project - see the repo root README for the full project context.

There is no real PCB for this tool head yet (see `../../hardware/`), so real
sensor capture isn't implemented. What's real and fully working today is the
processing pipeline those captures will feed: synthetic thermal/RGB frame
generation, false-color thermal rendering, real RGB->thermal ROI alignment
and stats extraction (`alignment.py`), and stats reporting - runs end-to-end
with no hardware attached, verified by 21 real pytest cases.

## Install & run

```bash
python3 -m venv .venv
# Linux/macOS:
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py selftest

# Windows:
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python main.py selftest
```

Or as an installed package (`pip install -e .` uses `pyproject.toml`, which
registers the `vision-companion` console script):

```bash
pip install -e .
vision-companion version
vision-companion selftest --out ./selftest_output
```

`selftest` generates a synthetic MLX9064x-shaped thermal frame (32x24, with a
soldering-tip-like hotspot) and a synthetic RGB color-bar test pattern,
renders/saves both (`thermal_frame.npy`, `thermal_frame_falsecolor.png`,
`rgb_frame.png`), and prints their stats - proof the numpy/Pillow pipeline
works end-to-end, independent of real hardware.

`analyze-roi X0 Y0 X1 Y1` maps an RGB-space bounding box (e.g. a component
detection from the Vision AI Node) into thermal-space, then reports real
min/max/mean temperature for that region - the alignment path the README's
"Eye-in-Hand Alignment" feature describes, exercised end-to-end today
against the synthetic thermal frame:

```bash
vision-companion analyze-roi 280 210 360 270
```

## Tests

```bash
pip install -e ".[dev]"
pytest
```

21 real pytest cases across `tests/test_main.py` (synthetic frame generation,
false-color rendering, CLI commands) and `tests/test_alignment.py` (ROI
coordinate mapping, out-of-bounds/degenerate-input guards, ROI stats
extraction).

See [main.py](main.py) and [alignment.py](alignment.py) for the real, working
code. A real MLX9064x/camera capture step will be added once hardware exists.
