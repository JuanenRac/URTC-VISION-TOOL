# vision_companion

Host-side (CM5 / dev machine) companion for **URTC-VISION-TOOL**'s dual-modal
thermal (MLX9064x) + RGB tool head. Part of the [URTC-VISION-TOOL](../../README.md)
project - see the repo root README for the full project context.

There is no real PCB for this tool head yet (see `../../hardware/`), so real
sensor capture isn't implemented. What's real and fully working today is the
processing pipeline those captures will feed: synthetic thermal/RGB frame
generation, false-color thermal rendering, and stats reporting - runs
end-to-end with no hardware attached.

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

See [main.py](main.py) for the real, working code. A real MLX9064x/camera
capture step will be added once hardware exists.
