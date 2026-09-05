# Changelog

All notable work on **URTC-VISION-TOOL** is summarized here, newest first.
Full This file intentionally omits calendar dates from individual entries.

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

## vision_companion [0.0.1] - Real RGB->thermal ROI alignment + temperature stats

- **`src/vision_companion/alignment.py`** (new) - the README's "Eye-in-Hand
  Alignment" feature, made real: `rgb_roi_to_thermal_roi()` rescales a
  bounding box detected in RGB-frame pixel space into the thermal sensor's
  much lower native resolution (assumes a shared field of view - a real
  per-pixel homography needs actual cameras to calibrate against, which
  don't exist yet), clamped and widened so it never collapses to a
  zero-size box; `extract_roi_stats()` pulls real min/max/mean temperature
  out of a thermal-frame region; `analyze_rgb_roi()` chains both into the
  end-to-end path a real component detection would drive.
- **`main.py`** - new `analyze-roi X0 Y0 X1 Y1` CLI command, runs the above
  against the existing synthetic thermal frame and prints real stats.
- **`tests/`** (new) - 21 real pytest cases across `test_main.py` (synthetic
  frame generation, false-color rendering, all 3 CLI commands) and
  `test_alignment.py` (ROI coordinate mapping, degenerate/out-of-bounds
  input guards, ROI stats extraction against real numpy arrays).
- **`pyproject.toml`** - added a `dev` extra (`pytest>=8`) and registered
  `alignment` as a packaged module; version bumped by hand to 0.0.1 per
  this package's own documented policy (no production build step exists
  yet for a Python tool this small - see the Versioning scheme above).
- Verified for real: `pip install -e ".[dev]"` + `pytest` -> 21/21 passed;
  `vision-companion analyze-roi 280 210 360 270` against the real synthetic
  thermal frame -> real min/max/mean temperature output.
- Still out of scope: real dual-modal capture (RGB camera + MLX9064x over
  I2C) and a real per-pixel calibration between the two sensors - both need
  a real PCB and real cameras that don't exist yet.

## [0.0.4] - Real sensor protocol: framing, CRC, range limits, rate limiting, field diagnostics

- **`src/sensor_frame.h`/`.c`** (new) - real wire framing for the sensor->MCU link (MLX9064x thermal camera / RGB trigger, once the PCB exists): `[SOF][VERSION][SENSOR_ID][SEQ][TIMESTAMP_MS][LEN][PAYLOAD][CRC8]`, with a real sensor-side millisecond timestamp field and the same real CRC-8 (poly 0x07) sibling repo URTC-SMART-RACK's own `protocol.c` uses. `sensor_frame_parse()` never partially trusts a frame - bad SOF, unsupported version, an out-of-range length, an incomplete/truncated buffer, and a real corrupted CRC (byte- or payload-level) are each their own distinct error. `sensor_frame_encode()` is the exact inverse.
- **`src/sensor_reading.h`/`.c`** (new) - `sensor_reading_validate_thermal()` decodes and range-checks a thermal payload against this project's own v0 real bounds (-40.00C to 300.00C, hundredths of a degree), separate from the framing layer - a well-formed frame can still carry a physically impossible reading (a real ADC glitch, a disconnected sensor reporting rail voltage).
- **`src/rate_limiter.h`/`.c`** (new) - `rate_limiter_allow()` real minimum-interval enforcement between accepted frames, so a malfunctioning/flooding sensor is throttled rather than trusted at whatever rate it happens to send.
- **`src/sensor_diagnostics.h`/`.c`** (new) - real, dedicated field-support counters (`frame_errors`, `out_of_range_count`, `rate_limited_count`, `disconnect_count`, `bus_reset_count`, `last_latency_ms`) that never make an accept/reject decision themselves - only `sensor_frame.c`/`sensor_reading.c`/`rate_limiter.c` do that, this module only records what they decided.
- **`tests/`** (new directory) - a minimal, dependency-free host-side test harness (`test_runner.h`, copied from sibling repo URTC-SMART-RACK's own convention), compiled with the *host's* C compiler, never `arm-none-eabi-gcc`. 65 real assertions across `test_sensor_frame.c` (19), `test_sensor_reading.c` (9), `test_rate_limiter.c` (6), `test_sensor_diagnostics.c` (14). **`test_vision_sensor_scenarios.c`** (17 assertions) is the real host-side sensor simulator the promotion audit asked for: it plays real encoded frames - valid, truncated, CRC-corrupted, a well-formed but out-of-range reading, a real too-fast resend, and a real explicit disconnection - through the whole real pipeline, confirming no reading is ever produced from corrupt/invalid data and that each real failure reason is recorded distinctly in the diagnostics counters.
- **`build_firmware.sh`/`.bat`** gained a new step 2 (renumbering the rest): builds and runs the host-native test suite before the version bump and the ARM cross-compile, failing the whole build if any assertion fails - same pattern sibling repo URTC-SMART-RACK already uses.
- Real verification note: this session's shell had no host `gcc`/`cc` on `PATH` (a real environment condition, previously documented for sibling repo URTC-SMART-RACK - not a project defect). Compiled and ran the exact same host-side test sources with the already-installed MSVC toolchain (`cl.exe`, VS2019 Build Tools) as a real substitute host compiler - `All tests passed.`, 0 failures. The `arm-none-eabi-gcc` cross-compile/link step (unaffected by this pass - `main.c` is untouched) was independently re-verified for real, producing `firmware/URTC_VISION_TOOL_FIRMWARE_v0.0.4.{bin,elf,hex}`.
- Still out of scope, on purpose: wiring `sensor_frame.c`/`sensor_reading.c`/`rate_limiter.c`/`sensor_diagnostics.c` into a real I2C/SPI receive path in `main.c` - there is still no PCB/MLX9064x/RGB trigger to receive real frames from.

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
