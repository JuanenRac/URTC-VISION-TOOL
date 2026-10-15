# Changelog

All notable work on **URTC-VISION-TOOL** is summarized here, newest first.
This file intentionally omits calendar dates from individual entries.

Two components are versioned on their own: the **firmware** (entries headed `[x.y.z]`) and
**vision_companion** (entries headed `vision_companion [x.y.z]`). Work that has not been given
a version yet is under **Unreleased**, first. After it come the firmware entries, newest first,
and then the vision_companion entries, newest first.

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

## Unreleased

**Firmware**

- **Fix standalone receive-path compilation.** Include `<stddef.h>` explicitly
  in `src/vision_sensor_link.c` so its disconnected-frame check has a definition
  of `NULL` when compiled as a separate translation unit. Fixes the GCC
  host-test build failure without changing receive-path behavior or
  incrementing either component version.
- **The real receive-path decision is now a real `src/` module.** New
  `src/vision_sensor_link.h`/`.c` (`vision_sensor_link_process_frame()`): the
  dispatch that chains the sensor frame, the reading check, the rate limiter and
  the diagnostics together existed only as a `static` function inside
  `tests/test_vision_sensor_scenarios.c`, not as a module anything else could
  call. It is promoted verbatim (same logic, same behavior) - the same gap and
  the same fix as in sibling repo URTC-SMART-RACK's `rack_link.c` - so the
  MLX9064x receive path is ready to wire into a real I2C/SPI ISR the day the PCB
  exists. `tests/test_vision_sensor_scenarios.c` now calls into this module
  instead of defining its own private copy of the logic under test, and the
  host-test step of `build_firmware.sh`/`.bat` compiles the new file alongside
  the existing ones.
  Verified: with no host `gcc`/`cc` on `PATH`, the whole host-side test suite
  (all 6 test files, all 5 `src/` modules including the new one) was compiled
  and run with the installed MSVC toolchain (`cl.exe`, VS2019 Build Tools) as a
  substitute host compiler, the same technique used for the 0.0.4 entry below:
  `All tests passed.`, 0 failures.

**Repository**

- **CI runs the vision_companion test suite on every push.**
  `.github/workflows/ci.yml` installs `src/vision_companion/requirements.txt`
  and runs its 27 pytest cases; before, CI only `py_compile`-checked them, so
  a regression there could not fail a build. The READMEs (all 7 languages) say
  so. No firmware or package code change, so no version bump (firmware 0.0.5,
  vision_companion 0.0.2 unchanged).

## [0.0.5] - Removed dangling references to a file that is not in this repository

`src/sensor_frame.h` and `src/sensor_reading.h` had comments that pointed to a
document (for the real MLX9064x I2C register map, still pending real
hardware) that is not tracked in this repo. The dangling pointer is removed;
the reasoning each comment already gave (a v0 convention, not a copy of the
real register map, pending real hardware/datasheet) stays intact and
self-sufficient without it.

Also carries a README (6 languages) correction - a stale hardcoded
`FIRMWARE_VERSION_MAJOR/MINOR/PATCH = 0.0.0` in the Directory Structure
comment, from earlier work, bundled here rather than left stranded.

Verified: the exact host-test command was compiled and run with MSVC
(`cl.exe`, VS2019 Build Tools) as the substitute host compiler (no `gcc`/`cc`
on `PATH`), as for the 0.0.4 entry below - `All tests passed.`, 0 failures.

## [0.0.4] - Real sensor protocol: framing, CRC, range limits, rate limiting, field diagnostics

- **`src/sensor_frame.h`/`.c`** (new) - real wire framing for the sensor->MCU link (MLX9064x thermal camera / RGB trigger, once the PCB exists): `[SOF][VERSION][SENSOR_ID][SEQ][TIMESTAMP_MS][LEN][PAYLOAD][CRC8]`, with a real sensor-side millisecond timestamp field and the same CRC-8 (poly 0x07) sibling repo URTC-SMART-RACK's own `protocol.c` uses. `sensor_frame_parse()` never partially trusts a frame - bad SOF, unsupported version, an out-of-range length, an incomplete/truncated buffer, and a corrupted CRC (byte- or payload-level) are each their own distinct error. `sensor_frame_encode()` is the exact inverse.
- **`src/sensor_reading.h`/`.c`** (new) - `sensor_reading_validate_thermal()` decodes and range-checks a thermal payload against this project's own v0 bounds (-40.00C to 300.00C, hundredths of a degree), separate from the framing layer - a well-formed frame can still carry a physically impossible reading (an ADC glitch, a disconnected sensor reporting rail voltage).
- **`src/rate_limiter.h`/`.c`** (new) - `rate_limiter_allow()` enforces a minimum interval between accepted frames, so a malfunctioning or flooding sensor is throttled rather than trusted at whatever rate it happens to send.
- **`src/sensor_diagnostics.h`/`.c`** (new) - dedicated field-support counters (`frame_errors`, `out_of_range_count`, `rate_limited_count`, `disconnect_count`, `bus_reset_count`, `last_latency_ms`) that never make an accept/reject decision themselves - only `sensor_frame.c`/`sensor_reading.c`/`rate_limiter.c` do that, this module only records what they decided.
- **`tests/`** (new directory) - a minimal, dependency-free host-side test harness (`test_runner.h`, copied from sibling repo URTC-SMART-RACK's convention), compiled with the *host's* C compiler, never `arm-none-eabi-gcc`. 65 assertions across `test_sensor_frame.c` (19), `test_sensor_reading.c` (9), `test_rate_limiter.c` (6), `test_sensor_diagnostics.c` (14). **`test_vision_sensor_scenarios.c`** (17 assertions) is a host-side sensor simulator: it plays encoded frames - valid, truncated, CRC-corrupted, a well-formed but out-of-range reading, a too-fast resend, and an explicit disconnection - through the whole pipeline, confirming no reading is ever produced from corrupt or invalid data and that each failure reason is recorded distinctly in the diagnostics counters.
- **`build_firmware.sh`/`.bat`** gained a new step 2 (renumbering the rest): builds and runs the host-native test suite before the version bump and the ARM cross-compile, failing the whole build if any assertion fails - the same pattern sibling repo URTC-SMART-RACK already uses.
- Verification note: the shell used had no host `gcc`/`cc` on `PATH` (an environment condition, previously documented for sibling repo URTC-SMART-RACK - not a project defect). The exact same host-side test sources were compiled and run with the installed MSVC toolchain (`cl.exe`, VS2019 Build Tools) as a substitute host compiler - `All tests passed.`, 0 failures. The `arm-none-eabi-gcc` cross-compile/link step (unaffected - `main.c` is untouched) was independently re-verified, producing `firmware/URTC_VISION_TOOL_FIRMWARE_v0.0.4.{bin,elf,hex}`.
- Still out of scope, on purpose: wiring `sensor_frame.c`/`sensor_reading.c`/`rate_limiter.c`/`sensor_diagnostics.c` into a real I2C/SPI receive path in `main.c` - there is still no PCB/MLX9064x/RGB trigger to receive real frames from.

## [0.0.3]

- Build version synchronized with `urtc.project.json` and the repository-native version source.

## [0.0.0] - Initial scaffolding (firmware)

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

The dual-modal capture (RGB camera + MLX9064x over I2C, synchronized
with the STM32 firmware over CAN) is the next milestone - it needs a real
PCB first.

## vision_companion [0.0.2] - An RGB ROI entirely outside the frame no longer reads as edge temperature

- **The bug.** `rgb_roi_to_thermal_roi()` clamped ANY projected thermal-space
  box into the frame's bounds, whether it genuinely overlapped the thermal
  frame or not. An RGB-space detection box entirely outside the RGB frame
  (or otherwise projecting somewhere with zero real overlap with the
  thermal sensor's field of view) still came back as a real, if narrow,
  in-bounds `BoundingBox` sitting right at whichever thermal edge was
  nearest - so `analyze_rgb_roi()` silently returned that edge pixel's
  temperature as if it were a real reading of the (nonexistent, off-frame)
  requested region, instead of reporting that there was no data at all.
- **The fix.** `rgb_roi_to_thermal_roi()` now returns `None` when the
  projected box has no real intersection with the thermal frame at all
  (a partially-overlapping box is still clamped to its real overlap, as
  before). `analyze_rgb_roi()` returns a new `RoiStats.empty()` sentinel
  in that case (`is_empty` True, `pixel_count == 0`, `min_c`/`max_c`/
  `mean_c` all NaN) instead of ever computing stats from a bogus clamped
  box. The `analyze-roi` CLI command reports "no thermal data" and exits
  1 for this case, instead of printing a real-looking temperature.
- 6 new tests across `test_alignment.py`/`test_main.py` (a box entirely
  past each frame edge, a genuinely partial-overlap box still clamping
  correctly, the empty-stats sentinel end to end, and the CLI's own
  no-data reporting) - confirmed to fail against the pre-fix code (5
  failures) via a local revert of just `alignment.py`/`main.py`, tests
  kept. 27/27 pytest cases pass with the fix (up from 21).
- Version 0.0.1 -> 0.0.2 (`vision_companion`'s own hand-bumped odometer -
  no production build step exists yet for this Python tool, see the
  Versioning scheme above).

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
- **`tests/`** (new) - 21 pytest cases across `test_main.py` (synthetic
  frame generation, false-color rendering, all 3 CLI commands) and
  `test_alignment.py` (ROI coordinate mapping, degenerate/out-of-bounds
  input guards, ROI stats extraction against real numpy arrays).
- **`pyproject.toml`** - added a `dev` extra (`pytest>=8`) and registered
  `alignment` as a packaged module; version bumped by hand to 0.0.1 per
  this package's own documented policy (no production build step exists
  yet for a Python tool this small - see the Versioning scheme above).
- Verified: `pip install -e ".[dev]"` + `pytest` -> 21/21 passed;
  `vision-companion analyze-roi 280 210 360 270` against the synthetic
  thermal frame -> min/max/mean temperature output.
- Still out of scope: real dual-modal capture (RGB camera + MLX9064x over
  I2C) and a real per-pixel calibration between the two sensors - both need
  a real PCB and real cameras that don't exist yet.

## vision_companion [0.0.0] - Initial CLI

**vision_companion (Python, host-side / CM5):**
- **`src/vision_companion/main.py`** - working CLI (`version`,
  `selftest`). `selftest` generates a synthetic MLX9064x-shaped thermal
  frame and a synthetic RGB color-bar test pattern, renders the thermal
  frame in false color, saves all outputs as real files, and prints
  stats - runs end-to-end today with zero hardware attached.
- **`src/vision_companion/pyproject.toml`** - packaging, registers the
  `vision-companion` console script (`pip install -e .`).
- **`src/vision_companion/requirements.txt`** - plain `pip install -r`
  alternative (numpy + pillow).
- Both install paths verified: `pip install -r requirements.txt`
  and `pip install -e .` (console script), `python main.py selftest` and
  `vision-companion selftest` both produce `.npy`/`.png` output.
