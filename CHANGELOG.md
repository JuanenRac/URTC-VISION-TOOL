# Changelog

All notable work on **URTC-VISION-TOOL**, newest first. This file leaves out calendar dates.

The repository has two parts with their own versions:

| Part | Where | Entries |
|---|---|---|
| **Firmware** (STM32, Cortex-M4F) | `src/*.c`, `src/*.h` | headed `## [x.y.z]` |
| **vision_companion** (Python, runs on a computer or the CM5) | `src/vision_companion/` | headed `## vision_companion [x.y.z]` |

The firmware entries come first, then those of vision_companion. Every entry says what was **Added**, **Changed**, **Fixed** and **Verified**, in that order, and only the headings that apply.

## Versioning scheme

The firmware (`FIRMWARE_VERSION_MAJOR`/`_MINOR`/`_PATCH` in `src/firmware_common.h`) and vision_companion (`version` in `src/vision_companion/pyproject.toml`) are versioned independently: they are built, shipped and run on entirely different targets. Both follow the family's "odometer" rule:

- the `PATCH` of the part that was built goes up by 1;
- when `PATCH` would pass 9 it goes back to 0 and `MINOR` goes up by 1 (`0.0.9` becomes `0.1.0`, never `0.0.10`);
- the same carry goes from `MINOR` into `MAJOR`.

The firmware is bumped by every run of `build_firmware.sh` / `build_firmware.bat` (`bump_version.py`, the same script URTC and URTC-SMART-RACK use). vision_companion is bumped by hand: there is no production build step for a Python tool this small yet.

---

# Firmware

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
- **`tests/`** - a small harness with no dependencies (`test_runner.h`, the convention of URTC-SMART-RACK), built with the host's C compiler and never with `arm-none-eabi-gcc`: 65 assertions in `test_sensor_frame.c` (19), `test_sensor_reading.c` (9), `test_rate_limiter.c` (6) and `test_sensor_diagnostics.c` (14), and `test_vision_sensor_scenarios.c` (17), a sensor simulator that plays valid, truncated, CRC-corrupted, out-of-range and too-fast frames and an explicit disconnection through the whole chain.
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
