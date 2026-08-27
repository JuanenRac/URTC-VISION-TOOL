# Changelog

All notable work on **URTC-VISION-TOOL** is summarized here, newest first.
Full session-by-session detail (including dates) lives in a private,
unpublished internal log - this file is public, so it intentionally omits
calendar dates.

## Versioning scheme

**Firmware** (`src/firmware_common.h`'s `FIRMWARE_VERSION_MAJOR`/`_MINOR`/`_PATCH`)
and **vision_companion** (`src/vision_companion/pyproject.toml`'s `version`)
are versioned independently - they build, ship, and run on entirely
different targets (STM32 vs. host/CM5). Both follow the same ecosystem-wide
base-10 "odometer" rule:

- the relevant component's `PATCH` +1 on every real build of that component
- when `PATCH` would exceed 9, it resets to 0 and `MINOR` +1 instead (e.g. `0.0.9` -> `0.1.0`, never `0.0.10`)
- the same carry cascades into `MAJOR` if `MINOR` would exceed 9

Firmware bumps automatically on every `build_firmware.sh`/`.bat` run (see
`bump_version.py`, the same generic script sibling repos URTC and
URTC-SMART-RACK use). `vision_companion` is bumped by hand today - no
production build step exists yet for a Python tool this small.

---

## [0.0.3]

- Build version synchronized with `hydra-umc.project.json` and the repository-native version source.

## [0.0.0] - Initial scaffolding

**Firmware (STM32, Cortex-M4F):**
- **`src/firmware_common.h`** - version identity. No pinout/hardware ID
  defined yet - there is no PCB for this board.
- **`src/startup_stm32_minimal.c`** / **`src/STM32_MINIMAL.ld`** - same
  hand-written vector table / placeholder linker script pattern as
  sibling repo URTC-SMART-RACK (copied rather than reinvented - identical
  situation: no real PCB yet to pin down the exact STM32 part).
- **`src/main.c`** - minimal proof-of-life entry point (heartbeat counter).
- **`build_firmware.sh` / `build_firmware.bat`** - real build: version
  bump, cross-compile with `arm-none-eabi-gcc` for Cortex-M4F, link,
  `objcopy` to `.bin`/`.hex`, size report, publish versioned artifacts to
  `firmware/`.

**vision_companion (Python, host-side / CM5):**
- **`src/vision_companion/main.py`** - real, working CLI (`version`,
  `selftest`). `selftest` generates a synthetic MLX9064x-shaped thermal
  frame and a synthetic RGB color-bar test pattern, renders the thermal
  frame in false color, saves all outputs as real files, and prints
  stats - runs end-to-end today with zero hardware attached.
- **`src/vision_companion/pyproject.toml`** - packaging, registers the
  `vision-companion` console script (`pip install -e .`).
- **`src/vision_companion/requirements.txt`** - plain `pip install -r`
  alternative (numpy + pillow).
- Both install paths verified for real: `pip install -r requirements.txt`
  and `pip install -e .` (console script), `python main.py selftest` and
  `vision-companion selftest` both produce real `.npy`/`.png` output.

The real dual-modal capture (RGB camera + MLX9064x over I2C, synchronized
with the STM32 firmware over CAN) is the next milestone - it needs a real
PCB first.
