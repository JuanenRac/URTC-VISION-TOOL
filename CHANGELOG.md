# Changelog

All notable work on **URTC-VISION-TOOL**, newest first. This file leaves out calendar dates.

The repository has two parts with their own versions:

| Part | Where | Entries |
|---|---|---|
| **Firmware** (STM32, Cortex-M4F) | `src/*.c`, `src/*.h` | headed `## [x.y.z]` |
| **vision_companion** (Python, runs on a computer or the CM5) | `src/vision_companion/` | headed `## vision_companion [x.y.z]` |

The firmware entries come first, then those of vision_companion. Every entry says what was **Added**, **Changed**, **Fixed** and **Verified**, in that order, and only the headings that apply.

## [Unreleased]

- The manifest declares how far the project has been shown to work (`evidence`: host-test) and `tools/ci_validate.py` checks the value.
- The manifest notes are shorter.
- The CI workflow no longer carries the steps for languages the repository does not use, and installs the newlib packages the firmware build needs.
- The README of each language lists URTC-UPDATER among the related projects.

## Versioning scheme

The firmware (`FIRMWARE_VERSION_MAJOR`/`_MINOR`/`_PATCH` in `src/firmware_common.h`) and vision_companion (`__version__` in `src/vision_companion/vision_companion/__init__.py`) are versioned independently: they are built, shipped and run on entirely different targets. Both follow the family's "odometer" rule:

- the `PATCH` of the part that was built goes up by 1;
- when `PATCH` would pass 9 it goes back to 0 and `MINOR` goes up by 1 (`0.0.9` becomes `0.1.0`, never `0.0.10`);
- the same carry goes from `MINOR` into `MAJOR`.

The firmware is raised only by the explicit `python bump.py` step (`bump_version.py`, the same script URTC and URTC-SMART-RACK use); building never changes it. vision_companion is bumped by hand: there is no production build step for a Python tool this small yet.

---

# Firmware

## [0.1.1] - An explicit bump command: building never changes the version

- Building no longer changes the firmware version: build_firmware.sh and build_firmware.bat only read it from src/firmware_common.h, and raising it is the explicit `python bump.py` step.
- Every licence statement and source header says GPL-3.0-or-later.

## [0.1.0] - A repeated or frozen frame is not a new reading, and builds undo a failed version bump

**Fixed**
- **A repeated, older or frozen frame is no longer accepted as a new reading.** The sequence number and the sensor timestamp of a frame were decoded and never used: the same frame sent twice, an old frame arriving late, and a sensor re-sending its last buffer all looked like a healthy stream. `src/sensor_freshness.h`/`.c` judges a frame against the last accepted one of the sensor (the sequence must be newer, with 8-bit wrap-around; the timestamp must have advanced, with 32-bit wrap-around). A repeat is counted in `replay_count`, a sequence that advances over a frozen timestamp in `stale_count`. The baseline only moves for an accepted frame, so a refused frame never spends the window of the good one that follows.
- **A payload of the wrong size is a malformed frame, not an impossible temperature:** it has its own counter (`malformed_payload_count`) instead of being counted as out of range.
- **The "latency" was an inter-arrival time.** `last_latency_ms` measured the time between two accepted frames; it is now `last_interarrival_ms`, and the new `last_sensor_latency_ms` is the receive time minus the sensor timestamp (meaningful only when both clocks share an epoch, which the header says).
- **The bytes of a parsed payload past its length are cleared.** A caller that reuses one frame variable no longer sees the tail of an earlier frame there.
- **The firmware image carries its version.** `g_firmware_version_code` was `volatile` but unreferenced, and the linker discarded it (`--gc-sections`); it now sits in a dedicated section that the linker script keeps, right after the vector table.
- **Start-up enables the FPU** before the first floating-point instruction (the image is built for the hard-float ABI), and a hard fault records the stacked registers and the fault status registers in RAM that survives a reset.
- **The Windows build honours `URTC_CI`** and no longer raises the version in a validation build; both build scripts work from any directory.

**Added**
- `vision_sensor_link_tick()` and `sensor_diagnostics_check_silence()`: a silence longer than a timeout is counted once per silence as a disconnect, and the freshness baseline is forgotten then, because a sensor that went quiet may come back with its counters restarted.
- The receive path takes the freshness state (`vision_sensor_link_process_frame()` has one more argument, and refuses when a state is missing); the order of the checks and the execution context (one context only, an interrupt only fills a ring buffer) are documented in `src/vision_sensor_link.h`.
- A build that fails after the version was raised puts the version, the manifest and the changelog back; every module is compiled for the Cortex-M4F target and all of them are linked together as a check; CI runs the host tests with AddressSanitizer and UBSan, and a pull request from the same repository no longer runs the workflow twice.
- `tests/test_project_consistency.py` fails when the host test sources of the two build scripts differ, when a module or a test file is missing from them, or when the README and manifest quote a stale number of assertions or pytest cases.
- `hardware/README.md` says what is undecided; `CONTRIBUTING.md` lists the target and interfaces as planned and not confirmed.

**Changed**
- The READMEs (all eight languages) state that the integration with URTC is planned and undecided, that the companion has no transport code yet, and the real test counts.
- `tools/build_test.py` selects the WSL distribution with `URTC_WSL_DISTRO`, says clearly when WSL or the ARM toolchain is missing, and also runs the pytest suite of the companion.
- The 0.0.4 entry no longer reads as if its four unit test files added up to 65 assertions.

**Verified**
- The host tests (154 assertions) with AddressSanitizer and UBSan and conversion warnings, the compile of every module and the link of the image for Cortex-M4F with the version word and the hard fault handler checked in the output, the unit tests of the build tooling, and both build scripts run on throwaway copies (validation mode, a failing compile that restores the version, and a full release-mode build). No run on real hardware.

## [0.0.9] - Claims aligned with what has been tested

- Maturity is functional: nothing here has been verified on real hardware yet.
- The README (all eight languages) renames the sensor protocol safety feature to range checks and says that they are pure C tested on a PC only, never run on a board or with a real sensor, and not a safety function.

## [0.0.8] - Firmware published only as release assets

- Firmware binaries (bin, elf, hex) are no longer versioned in git; they are published only as assets of the GitHub release of each version. build_firmware.sh and build_firmware.bat write them to firmware/ (git-ignored) in release mode and to build/firmware in CI mode.
- New tools/publish_release_assets.py checks the files in firmware/, writes the missing sha256 sidecar and prints the exact gh release create command with the files to attach; tests/test_publish_release_assets.py covers it. The READMEs (8 languages) describe the new flow.
- Verified: unit tests, the repository validation and a full ARM build in release mode. No behaviour of the firmware itself changed.

## [0.0.7] - Firmware version boundaries and side-effect-free CI builds

- The firmware version scripts keep their own three-component odometer (0.7.9 -> 0.8.0, 0.9.9 -> 1.0.0, 9.9.9 -> 10.0.0) and no longer hand over to the shared manifest utility, which broke the build at the boundary versions; the successor rule is now a pure function covered by boundary tests that run in CI and as a step of the build script.
- CI builds (URTC_CI=1) publish firmware images under build/firmware instead of firmware/, so a validation build leaves the tracked images untouched.
- Verified: unit tests and shell syntax checks only; the ARM firmware build itself was not run.

## [0.0.6] - A frame of another sensor is never taken for a temperature, and a bad frame does not use up the good one's window

**Fixed**
- **Only the thermal camera is read on this link.** The sensor id of a frame was never checked, so any frame with a valid CRC and two bytes of payload (the RGB trigger, or an id nobody knows) was taken for a temperature. Those frames are now counted apart (`unsupported_sensor_count`) and never reach the reading validation.
- **The content is checked before the rate limiter is spent.** A frame with an out-of-range reading used to use up the window, so the next, good frame looked too fast and was dropped.

**Added**
- **The receive-path decision is a module of `src/`.** `src/vision_sensor_link.h`/`.c` (`vision_sensor_link_process_frame()`) chains the sensor frame, the reading check, the rate limiter and the diagnostics. Until now it existed only as a `static` function inside `tests/test_vision_sensor_scenarios.c`, so nothing else could call it. It was promoted with the same logic (the same fix as `rack_link.c` in URTC-SMART-RACK), so the MLX9064x receive path is ready to be wired to an I2C/SPI interrupt the day the PCB exists. The scenario tests now call into the module instead of carrying a private copy, and the host-test step of `build_firmware.sh`/`.bat` compiles it.
- Two scenarios in the host tests: a frame of another sensor, and a bad frame followed by a good one.

**Fixed (build)**
- `src/vision_sensor_link.c` includes `<stddef.h>` explicitly, so its disconnected-frame check has `NULL` when compiled as a separate unit (it broke the host-test build with GCC; the behaviour did not change).

**Repository**
- CI runs the 27 pytest cases of vision_companion on every push (`.github/workflows/ci.yml` installs `src/vision_companion/requirements.txt`); before, it only byte-compiled them, so a regression there could not fail a build. The READMEs, in all the languages, say so.

**Verified**
- The whole host-side suite (6 test files, 5 `src/` modules plus the new one) was compiled and run: `All tests passed.`

## [0.0.5] - Removed dangling references to a file that is not in this repository

**Changed**
- `src/sensor_frame.h` and `src/sensor_reading.h` had comments pointing to a document (the real MLX9064x I2C register map, still pending real hardware) that is not tracked here. The pointer is gone; the reasoning of each comment (a v0 convention, not a copy of the real register map, pending hardware and datasheet) stays whole without it.
- The READMEs lost a stale hard-coded `FIRMWARE_VERSION_MAJOR/MINOR/PATCH = 0.0.0` in the Directory Structure comment.

**Verified**
- The exact host-test command was compiled and run with MSVC (`cl.exe`, VS2019 Build Tools) as the host compiler, as for 0.0.4: `All tests passed.`

## [0.0.4] - Real sensor protocol: framing, CRC, range limits, rate limiting, field diagnostics

**Added**
- **`src/sensor_frame.h`/`.c`** - the wire framing of the sensor-to-MCU link (MLX9064x thermal camera and RGB trigger, once the PCB exists): `[SOF][VERSION][SENSOR_ID][SEQ][TIMESTAMP_MS][LEN][PAYLOAD][CRC8]`, with a sensor-side millisecond timestamp and the CRC-8 (polynomial 0x07) that URTC-SMART-RACK's `protocol.c` uses. `sensor_frame_parse()` never half-trusts a frame: a bad SOF, an unsupported version, an out-of-range length, a truncated buffer and a corrupted CRC are each their own error. `sensor_frame_encode()` is its exact inverse.
- **`src/sensor_reading.h`/`.c`** - `sensor_reading_validate_thermal()` decodes a thermal payload and checks it against this project's v0 limits (-40.00 to 300.00 C, in hundredths), apart from the framing: a well-formed frame can still carry an impossible reading (an ADC glitch, a disconnected sensor reporting the rail voltage).
- **`src/rate_limiter.h`/`.c`** - `rate_limiter_allow()` keeps a minimum interval between accepted frames, so a faulty or flooding sensor is throttled instead of trusted at whatever rate it sends.
- **`src/sensor_diagnostics.h`/`.c`** - counters for field support (`frame_errors`, `out_of_range_count`, `rate_limited_count`, `disconnect_count`, `bus_reset_count`, `last_latency_ms`). They never decide anything; they only record what the other modules decided.
- **`tests/`** - a small harness with no dependencies (`test_runner.h`, the convention of URTC-SMART-RACK), built with the host's C compiler and never with `arm-none-eabi-gcc`: 65 assertions: 48 in four unit test files (`test_sensor_frame.c` 19, `test_sensor_reading.c` 9, `test_rate_limiter.c` 6 and `test_sensor_diagnostics.c` 14) and 17 in `test_vision_sensor_scenarios.c`, a sensor simulator that plays valid, truncated, CRC-corrupted, out-of-range and too-fast frames and an explicit disconnection through the whole chain.
- **`build_firmware.sh`/`.bat`** have a new step 2 that builds and runs the host tests before the version bump and the ARM cross-compile, and fail the whole build if one assertion fails.

**Verified**
- The shell had no host `gcc`/`cc`; the same sources were compiled and run with MSVC (`cl.exe`, VS2019 Build Tools): `All tests passed.` The ARM cross-compile and link (`main.c` is untouched) produced `firmware/URTC_VISION_TOOL_FIRMWARE_v0.0.4.{bin,elf,hex}`.

**Not done on purpose**
- Wiring those modules to an I2C/SPI receive path in `main.c`: there is no PCB, MLX9064x or RGB trigger to receive real frames from yet.

## [0.0.3]

**Changed**
- The build version follows `urtc.project.json` and the repository's own version source.

## [0.0.0] - Initial scaffolding (firmware)

**Added**
- `src/firmware_common.h` - the version identity. No pinout or hardware id yet: there is no PCB for this board.
- `src/startup_stm32_minimal.c` and `src/STM32_MINIMAL.ld` - the hand-written vector table and placeholder linker script of URTC-SMART-RACK, copied instead of reinvented (the same situation: no PCB yet to fix the exact STM32 part).
- `src/main.c` - a minimal proof of life (a heartbeat counter).
- `build_firmware.sh` / `build_firmware.bat` - the build: version bump, cross-compile with `arm-none-eabi-gcc` for Cortex-M4F, link, `objcopy` to `.bin`/`.hex`, size report, versioned artifacts published to `firmware/`.

**Next milestone**
- The dual-modal capture (RGB camera plus MLX9064x over I2C, synchronised with the STM32 firmware over CAN); it needs a real PCB first.

---

# vision_companion

## vision_companion [0.0.3] - Package layout, invalid pixels, sensor variants and a command line that fails cleanly

**Changed**
- The code is a package, `src/vision_companion/vision_companion/` (`cli.py`, `alignment.py`), instead of the top-level modules `main` and `alignment`, which installed two generic module names into site-packages. `python -m vision_companion` runs it, the `vision-companion` script points to `vision_companion.cli:main`, and the version is defined once, in `vision_companion/__init__.py` (`pyproject.toml` reads it). `pyproject.toml` asks for setuptools 77 or newer, which the SPDX license string needs.
- A degenerate region exits `2` with a one-line message instead of a traceback, the same code as a usage error; a region that reaches past the RGB frame is measured on the part inside it, with a warning on stderr. The exit codes are `0` ok, `1` no thermal data, `2` invalid usage or input.

**Fixed**
- **One NaN pixel no longer turns the statistics of a region into NaN.** Pixels that are not finite are left out of `min_c`/`max_c`/`mean_c`, are not counted in `pixel_count` and are reported in the new `invalid_pixel_count`; a region without a valid pixel is empty.
- **A uniform frame is no longer drawn as the coldest pixel:** the false-color scale is never narrower than 1 degree, and pixels without a valid temperature are painted magenta instead of turning the whole image black.

**Added**
- `p95_c`, the 95th percentile of a region (a hot-spot figure that one spurious hot pixel cannot move), printed by `analyze-roi`.
- `--variant 90640|90641|90642` on `selftest` and `analyze-roi` (32x24, 16x12 and 32x24 pixels), and `--range LOW HIGH` on `selftest` for a fixed false-color scale.
- `constraints.txt` (upper bounds of the dependencies, used by CI), `ruff` in CI, and `tests/test_docs.py`, which checks that `docs/CLI_REFERENCE.md` names the current version, every command and option and the exit codes.

**Verified**
- 50 pytest cases (27 before) and `ruff check` pass; the CLI reference was rewritten from real runs of the command.

**Version**
- 0.0.2 to 0.0.3, bumped by hand (see the versioning scheme above).

## vision_companion [0.0.2] - An RGB region entirely outside the frame no longer reads as edge temperature

**Fixed**
- `rgb_roi_to_thermal_roi()` clamped any projected box into the bounds of the thermal frame, whether it overlapped it or not. A detection box entirely outside the RGB frame (or projecting where the thermal sensor sees nothing) still came back as a narrow box at the nearest thermal edge, so `analyze_rgb_roi()` returned that edge pixel's temperature as if it were a reading of the requested, non-existent region.
- It now returns `None` when the projected box has no real overlap with the thermal frame (a box that partly overlaps is still clamped to its real overlap, as before). `analyze_rgb_roi()` then returns a new `RoiStats.empty()` (`is_empty` true, `pixel_count == 0`, `min_c`/`max_c`/`mean_c` all NaN) instead of computing statistics from an invented box. The `analyze-roi` command says "no thermal data" and exits with 1, instead of printing a temperature that looks real.

**Verified**
- 6 new tests in `test_alignment.py` and `test_main.py` (a box past each edge, a box that partly overlaps, the empty result from end to end, and what the command says). They fail against the old code (5 failures, checked by reverting only `alignment.py` and `main.py`) and pass with the fix: 27 of 27 (before 21).

**Version**
- 0.0.1 to 0.0.2, bumped by hand (see the versioning scheme above).

## vision_companion [0.0.1] - RGB-to-thermal region alignment and temperature statistics

**Added**
- `src/vision_companion/alignment.py` - the "Eye-in-Hand Alignment" of the README, made real: `rgb_roi_to_thermal_roi()` rescales a box detected in RGB pixels to the much lower native resolution of the thermal sensor (it assumes a shared field of view: a per-pixel homography needs real cameras to calibrate against), clamped and widened so it never collapses to zero size; `extract_roi_stats()` takes the minimum, maximum and mean temperature of a region of a thermal frame; `analyze_rgb_roi()` chains both into the path a real component detection will drive.
- `main.py` - the `analyze-roi X0 Y0 X1 Y1` command, which runs the above on the synthetic thermal frame and prints the statistics.
- `tests/` - 21 pytest cases in `test_main.py` (synthetic frame, false-colour rendering, the three commands) and `test_alignment.py` (coordinate mapping, degenerate and out-of-bounds inputs, statistics on real numpy arrays).
- `pyproject.toml` - a `dev` extra (`pytest>=8`) and `alignment` registered as a packaged module.

**Verified**
- `pip install -e ".[dev]"` and `pytest`: 21 of 21. `vision-companion analyze-roi 280 210 360 270` on the synthetic frame printed the minimum, maximum and mean temperature.

**Not done on purpose**
- The dual-modal capture (RGB camera plus MLX9064x over I2C) and a per-pixel calibration between the two sensors: both need a real PCB and real cameras.

## vision_companion [0.0.0] - Initial command line

**Added**
- `src/vision_companion/main.py` - a working command line (`version`, `selftest`). `selftest` makes a synthetic MLX9064x-shaped thermal frame and an RGB colour-bar test pattern, renders the thermal frame in false colour, saves every output as a file and prints statistics: it runs from end to end with no hardware.
- `src/vision_companion/pyproject.toml` - the packaging, with the `vision-companion` console script (`pip install -e .`).
- `src/vision_companion/requirements.txt` - the plain `pip install -r` alternative (numpy and pillow).

**Verified**
- Both ways of installing work, and `python main.py selftest` and `vision-companion selftest` write the `.npy` and `.png` outputs.
