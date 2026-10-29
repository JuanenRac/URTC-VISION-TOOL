# Changelog

All notable changes to this project are documented here.

## [Unreleased]

- **Related Projects lists the URTC family:** the section names the repositories of URTC by group, each with one short line about what it is for, and, in one short line each, the sister projects (independent ecosystems of the same author that share the base and the tools), in the eight languages. It no longer says that URTC is part of another ecosystem. `CONTRIBUTING.md` places the tool head in the URTC ecosystem.
- **The number of pytest cases of the companion is the number that pytest collects** (183, a parametrized test counts once for each value) in the manifest and in the READMEs, and the test that keeps them honest now counts the collected cases instead of the test functions.
- **The README follows the universal layout in the eight languages:** the sections are in the fixed order with the fixed names, the vision tool flow is drawn from `docs/architecture.json` (the Mermaid source stays in a collapsible block), the Repository Structure comes from `docs/structure.json`, and the sections for role, security, interfaces, testing and roadmap are new. The number of companion test cases is current (183).
- **The layout of the README is checked in the CI:** the validator runs `tools/universal_readme_check.py` and lists, as a warning, what differs from the universal layout of the README.
- **Project status is the second section of the README,** right after At a glance, in the eight languages.
- **The full CI runs every night:** a scheduled workflow runs the complete baseline again on the default branch and opens (or updates) one issue when it fails, so a change in a runner image, a toolchain or a pinned dependency is found the next day instead of with the next unrelated change.
- **The receive path is ready for an interrupt:** `sensor_rx.c` puts the bytes an interrupt receives in a single-producer ring (the shared `urtc_ring.h`), and the main loop finds the frames in them, resynchronises after a damaged one and drops a half frame that waited too long, so the rate limiter, the freshness state and the diagnostics are only touched from one context and never read half updated. It is played byte by byte in the host tests, with the sanitizers, and compiles for the target. The test count is current (190 checks in 10 files).
- **One list of host test sources:** `tools/host_sources.txt` is read by both build scripts, so a source or a test file is added in one place and the Linux and Windows builds can no longer differ.

## [0.1.5] - The rack check closes the loop of the pre-heat and the README files carry sections written once in URTC-COMMON

- **`capture`: the thermal image of a URTC head through a serial CAN adapter:** `vision-companion capture --port PORT` runs the exchange of `urtc_thermal.py` (`0x250` to `0x255`: start, poll until ready, 48 chunks of four frames, or 12 for the 90641) over an SLCAN adapter (`slcan_link.py`: `C`, `S6`, `O`, the frames as `t` lines; a serial port or a pyserial URL) and saves `thermal_frame.npy` and the false-colour PNG like `selftest` does, so `inspect`, `drift-check` and `rack-check` can take the file. A head that reports an error, never becomes ready or leaves a chunk unanswered ends the command with exit code 1 and a message; a port that cannot be opened, pyserial missing or a bit rate SLCAN does not have ends it with 2. pyserial is now a dependency. 27 tests play a simulated head through a simulated adapter that listens on a local TCP port (`tests/slcan_adapter.py`; pyserial opens `socket://` like a port, so the bytes are real): the image comes back within a hundredth of a degree, the commands of the adapter come in order, a head that needs several polls is waited for, the frames of a chunk that come one by one on a slow line are put together, noise and frames of other nodes on the line are ignored, a lost frame names its chunk, and a saved capture is judged by `inspect`. Not run against a real adapter, bus or head.
- **The rack check closes the loop of the pre-heat:** `rack-watch` judges a series of frames taken while the rack heats and reports, per slot, the last verdict, when the target was first reached and whether a swap is allowed (`swap_ok` needs the last three readings at the target, `swap_wait` while the tip is not stable or has no reading, `swap_blocked` after a fault); `rack-simulate` writes the frames of a simulated rack (healthy, slow heater, overshoot, heater in an empty slot, dead region) so the whole loop runs without a camera or a rack. `rack-check` and `rack-watch` print their words in eight languages (`--lang en|es|de|fr|it|ja|zh|pt`) from one table that a test holds complete; the verdicts in JSON and the exit codes do not change. 13 new tests; the CLI reference describes the commands.
- **The README files carry sections written once in URTC-COMMON:** "Compatibility", in the eight languages, between marker comments before the license heading (`tools/readme_sections.py` of URTC-COMMON writes and checks them; the rest of each README is hand-written as before).
- **A static check on every push:** `ruff.toml` (unused names, exception chaining and syntax errors, the rules the flasher and the tester already ran) and a step of the CI that runs `ruff check .` with a pinned ruff; nothing to fix.
- **The frame layer and the rate limiter come from URTC-COMMON:** `sensor_frame_parse` and `sensor_frame_encode` use `src/urtc_frame.h`, shared with the tool rack, and `rate_limiter.c` calls `src/urtc_rate_limiter.h` (both copied with `vendor_copy.py --set firmware_frame`); the names, the order of the checks and every decision are unchanged. The tests of the limiter also run the shared decisions (`tests/vectors/rate_vectors.h`, copied with `--set rate_c`), the wrap of the millisecond counter included, with the sanitizers.
- The `TEST_ASSERT` macro of the host tests comes from URTC-COMMON (`tests/vectors/urtc_test.h`, copied with `vendor_copy.py --set firmware_test`) instead of being written again in `tests/test_runner.h`; the suites are unchanged.
- **The host tests are held to a coverage floor:** the CI builds them with gcov counters (`URTC_COVERAGE_FLOOR` in `build_firmware.sh`) and `tools/gcov_floor.py` fails the build when they execute less than 92 percent of the lines of `src/` (100 percent today).
- The CI holds the `vision_companion` tests to a coverage floor of 88 percent (measured 96).
- **The sensor frame is big-endian, version 2:** the timestamp of the frame and the thermal reading it carries were little-endian, unlike every other multi-byte value of the family. `SENSOR_FRAME_VERSION` is now 2, `sensor_frame.c` writes and reads the four timestamp bytes most significant first and `sensor_reading_validate_thermal()` reads the signed 16-bit reading the same way. A frame of version 1 is refused as an unsupported version instead of being read as another timestamp or another temperature (a reading of 1.00 degree sent the old way, bytes `64 00`, would otherwise have been read as 25600 hundredths, 256.00 degrees, and accepted).
- **The frame is held to vectors written by URTC-COMMON:** `tests/test_sensor_vectors.c` encodes and parses every frame of `tests/vectors/sensor_vectors.h` (copied with `vendor_copy.py`, lock updated), reproduces every parse outcome including the refusal of version 1, and checks every thermal reading, so the firmware and the reference model of URTC-COMMON cannot drift apart unnoticed. The host test harness builds it in `build_firmware.sh` and `build_firmware.bat`; the existing tests build their payloads big-endian.

## [0.1.4] - Vision frames use the CRC-8 shared with the rack and checked against the shared vectors

- **One checksum for the vision link and the rack:** `sensor_frame_crc8()` now calls `urtc_crc8()` of `src/urtc_crc8.h`, the header that URTC-COMMON keeps for the repositories that frame their data with CRC-8 (copied with `vendor_copy.py`, locked in `src/urtc_common.lock.json`); the test checks it against the check values URTC-COMMON computes on its own, among them the CRC-8 check value `0xF4` of the text `123456789`. The host tests run 156 assertions.

## [0.1.3] - Plan inspection, series export, drift check and rack check

- **`inspect`**: judges each component of a plan (regions found in the RGB image) by the temperature rule of its kind (expected value with tolerance, minimum, maximum, rise over the ambient): cold joints, parts that run hot, regions without data are never ok. The report can be written as JSON.
- **Series export of the regions**: the minimum, maximum, mean and 95th percentile of every region and task as samples for the HYDRA-UMC datalake (`--datalake URL`, the token read from an environment variable and never printed), as JSON lines (`--export-jsonl`) or as a map of OPC-UA node values (`--opcua-nodes`).
- **`drift-check`**: compares frames of a reference scene with a stored baseline (dead pixels, stuck or noisy pixels, offset drift) and can write a calibration file that the other commands accept (`--suggest-calibration`).
- **`rack-check`**: judges the tips of the tool rack from a thermal frame (reached, too slow, overshoot, a heater on in an empty slot), with the rules of URTC-SMART-RACK checked against shared cases.
- The false colour of this program is checked against the shared vectors of URTC-COMMON within one level. Exit code 3 means a finding. New tests cover the plan, the verdicts, the export (also against a local server), the drift and the commands; the lint and the type check are clean.
- The README lists URTC-GATEWAY, the new gateway in front of the CAN bus, among the related projects.

## [0.1.2] - The thermal tool on the URTC bus, a calibration file and a Windows build

- `tools/ci_validate.py` fails when a versioned file has the name of a Windows path (a colon, the character a file system uses to store one, or a first folder named like a drive or a user profile): a path handed to WSL without translation once put build output inside a repository. The same check (`tools/_tracked_names.py`) is in every URTC repository.
- The `build-test` scripts use the interpreter named by `URTC_PYTHON` (which URTC-UPDATER sets to its own) and, without it, the first `python3` or `py -3` found, so a build check runs with a Python whose packages are known.
- **The vision head reuses the thermal inspection tool of URTC** (tool profile 22, CAN identifiers `0x250`-`0x255`) instead of defining a second protocol for the image. `vision_companion/urtc_thermal.py` is the host side of that exchange: it builds the trigger, status and chunk requests, reads the answers (four frames of eight bytes per chunk of 16 big-endian `int16` values in hundredths of a degree), puts the chunks back together row by row (48 chunks for a 32x24 sensor, 12 for a 16x12 one) and reports an incomplete chunk instead of a wrong image. `SimulatedThermalHead` answers like a head (busy then ready, no answer before ready, values clamped to the `int16` range) so the whole exchange is tested without hardware; `read_frame()` runs a capture over two callables, so any CAN library can carry it. The README of every language, `hardware/README.md` and the companion README say that the integration is decided; the sensor-side frame protocol of the firmware stays as a separate, host-tested building block that does not carry the image.
- The pytest suite has 13 more cases for these messages (75 in total).
- The CI workflow also builds and tests on Windows (the `.bat` build script with the ARM toolchain, and the companion tests), keeps the firmware images of both builds as workflow artifacts and pins its actions to a commit.
- The dashboard notice is sent only after the CI of the push finished green.
- **`--calibration FILE` on `selftest` and `analyze-roi`** (`vision_companion/calibration.py`): a JSON file with a gain, an offset, a per-pixel offset map and a list of dead pixels is applied to the thermal frame before it is drawn or measured; dead pixels are counted as invalid, an unknown key, a map of the wrong size or a bad value is refused with exit code 2. 12 new tests (62 in all); the CLI reference describes the file.
- The banner follows the animated style of the ecosystem banners, with the name, the kind and the technologies of the project.
- **CI type-checks the `vision_companion` package with `mypy`** next to the tests and `ruff`; the package already passes with no issue.
- The manifest declares how far the project has been shown to work (`evidence`: host-test) and `tools/ci_validate.py` checks the value.
- The manifest notes are shorter.
- The CI workflow no longer carries the steps for languages the repository does not use, and installs the newlib packages the firmware build needs.
- The README of each language lists URTC-UPDATER among the related projects.

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

- The firmware version scripts keep their own three-component scheme and no longer hand over to the shared manifest utility, which broke the build at the boundary versions; the successor rule is now a pure function covered by boundary tests that run in CI and as a step of the build script.
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

## Earlier history

### vision_companion [0.0.3] - Package layout, invalid pixels, sensor variants and a command line that fails cleanly

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

### vision_companion [0.0.2] - An RGB region entirely outside the frame no longer reads as edge temperature

**Fixed**
- `rgb_roi_to_thermal_roi()` clamped any projected box into the bounds of the thermal frame, whether it overlapped it or not. A detection box entirely outside the RGB frame (or projecting where the thermal sensor sees nothing) still came back as a narrow box at the nearest thermal edge, so `analyze_rgb_roi()` returned that edge pixel's temperature as if it were a reading of the requested, non-existent region.
- It now returns `None` when the projected box has no real overlap with the thermal frame (a box that partly overlaps is still clamped to its real overlap, as before). `analyze_rgb_roi()` then returns a new `RoiStats.empty()` (`is_empty` true, `pixel_count == 0`, `min_c`/`max_c`/`mean_c` all NaN) instead of computing statistics from an invented box. The `analyze-roi` command says "no thermal data" and exits with 1, instead of printing a temperature that looks real.

**Verified**
- 6 new tests in `test_alignment.py` and `test_main.py` (a box past each edge, a box that partly overlaps, the empty result from end to end, and what the command says). They fail against the old code (5 failures, checked by reverting only `alignment.py` and `main.py`) and pass with the fix: 27 of 27 (before 21).

**Version**
- 0.0.1 to 0.0.2, bumped by hand (see the versioning scheme above).

### vision_companion [0.0.1] - RGB-to-thermal region alignment and temperature statistics

**Added**
- `src/vision_companion/alignment.py` - the "Eye-in-Hand Alignment" of the README, made real: `rgb_roi_to_thermal_roi()` rescales a box detected in RGB pixels to the much lower native resolution of the thermal sensor (it assumes a shared field of view: a per-pixel homography needs real cameras to calibrate against), clamped and widened so it never collapses to zero size; `extract_roi_stats()` takes the minimum, maximum and mean temperature of a region of a thermal frame; `analyze_rgb_roi()` chains both into the path a real component detection will drive.
- `main.py` - the `analyze-roi X0 Y0 X1 Y1` command, which runs the above on the synthetic thermal frame and prints the statistics.
- `tests/` - 21 pytest cases in `test_main.py` (synthetic frame, false-colour rendering, the three commands) and `test_alignment.py` (coordinate mapping, degenerate and out-of-bounds inputs, statistics on real numpy arrays).
- `pyproject.toml` - a `dev` extra (`pytest>=8`) and `alignment` registered as a packaged module.

**Verified**
- `pip install -e ".[dev]"` and `pytest`: 21 of 21. `vision-companion analyze-roi 280 210 360 270` on the synthetic frame printed the minimum, maximum and mean temperature.

**Not done on purpose**
- The dual-modal capture (RGB camera plus MLX9064x over I2C) and a per-pixel calibration between the two sensors: both need a real PCB and real cameras.

### vision_companion [0.0.0] - Initial command line

**Added**
- `src/vision_companion/main.py` - a working command line (`version`, `selftest`). `selftest` makes a synthetic MLX9064x-shaped thermal frame and an RGB colour-bar test pattern, renders the thermal frame in false colour, saves every output as a file and prints statistics: it runs from end to end with no hardware.
- `src/vision_companion/pyproject.toml` - the packaging, with the `vision-companion` console script (`pip install -e .`).
- `src/vision_companion/requirements.txt` - the plain `pip install -r` alternative (numpy and pillow).

**Verified**
- Both ways of installing work, and `python main.py selftest` and `vision-companion selftest` write the `.npy` and `.png` outputs.
