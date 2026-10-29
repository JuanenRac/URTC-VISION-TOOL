# Source map

Every file of the repository with a line on what it does: the annotated tree that the README carried before it was reduced to the first level (the first level, in eight languages, is in the section Repository Structure of the README).

```text
URTC-VISION-TOOL/
├── src/
│   ├── firmware_common.h           # FIRMWARE_VERSION_MAJOR/MINOR/PATCH
│   ├── sensor_frame.h / .c         # Real: versioned frame format + CRC8 parse/encode
│   ├── urtc_crc8.h                 # Real: CRC-8 shared with the tool rack (copied from URTC-COMMON)
│   ├── urtc_frame.h                # Real: frame layer shared with the tool rack (copied from URTC-COMMON)
│   ├── urtc_rate_limiter.h         # Real: minimum-interval limiter of the link (copied from URTC-COMMON)
│   ├── sensor_reading.h / .c       # Real: thermal reading decode + range validation
│   ├── rate_limiter.h / .c         # Real: minimum-interval frame throttling
│   ├── sensor_freshness.h / .c     # Real: sequence/timestamp freshness (replay and stale-sensor detection)
│   ├── sensor_diagnostics.h / .c   # Real: error/latency/bus-reset counters, separate from control
│   ├── vision_sensor_link.h / .c   # Real: frame-dispatch decision tying sensor_frame/sensor_reading/rate_limiter/sensor_diagnostics together
│   ├── main.c                      # Minimal entry point (proof-of-life heartbeat loop)
│   ├── startup_stm32_minimal.c     # Vector table + Reset_Handler (no ST HAL yet, see file header)
│   ├── STM32_MINIMAL.ld            # Placeholder linker script (128K FLASH / 32K RAM floor)
│   └── vision_companion/           # Host-side (CM5/dev machine) Python vision pipeline
│       ├── pyproject.toml          # Packaging + `vision-companion` console script
│       ├── requirements.txt        # numpy + pillow
│       ├── vision_companion/
│       │   ├── __init__.py         # The companion's version, defined once
│       │   ├── cli.py              # Real, working CLI (version / selftest / analyze-roi / capture / inspect / drift-check / rack-check / rack-watch / rack-simulate)
│       │   ├── alignment.py        # Real: RGB<->thermal ROI mapping + temperature-stats extraction
│       │   ├── calibration.py      # Real: thermal calibration (gain, offsets, dead pixels) loaded from JSON
│       │   ├── urtc_thermal.py     # Real: reads a thermal image from a URTC head over CAN (0x250-0x255), with a simulated head
│       │   ├── slcan_link.py       # Real: the SLCAN serial adapter that carries it (used by `capture`)
│       │   ├── inspection.py       # Real: judges the components of a plan by temperature, exports the series
│       │   ├── export.py           # Real: JSON Lines, OPC UA node list and DataLake export of the readings
│       │   ├── sensor_drift.py     # Real: drift of a sensor against a saved baseline
│       │   ├── rack_check.py       # Real: per-slot verdict of the pre-heat of a rack
│       │   ├── rack_watch.py       # Real: the same over a series of frames, says when a swap is allowed
│       │   └── rack_text.py        # Real: the words of the rack check in the eight languages
│       ├── tests/                  # 135 real pytest cases (the whole companion)
│       └── README.md               # Companion-specific usage docs
├── tests/                          # Real host-native firmware test harness (sensor_frame, sensor_reading, rate_limiter, sensor_diagnostics, sensor scenarios, freshness, robustness)
├── docs/                           # Command line reference (CLI_REFERENCE.md)
├── hardware/                       # Hardware notes (README.md) - no design files yet (no schematic, no PCB)
├── firmware/                       # Build output (.bin/.elf/.hex), git-ignored - published only as assets of the GitHub release
├── build/                          # Intermediate build objects (gitignored)
├── images/                         # Media and diagrams
├── tools/
│   ├── build_test.py               # Non-versioning build/compile check
│   ├── gcov_floor.py               # Fails when the host tests run less of src/ than a floor (gcov)
│   ├── publish_release_assets.py   # Lists the release assets to attach and prints the gh command
│   ├── ci_validate.py              # Manifest/CHANGELOG/docs validation used by CI
│   └── _doc_policy.py / _readme_parity.py / _tracked_names.py # Shared checks used by ci_validate.py
├── bump.py                         # Explicit version bump command (building never bumps)
├── bump_version.py                 # version bump (generic, shared with URTC / URTC-SMART-RACK), called by bump.py
├── bump_manifest_version.py        # Syncs urtc.project.json's version to the native one (--sync)
├── build_firmware.sh / .bat        # Real build: host tests + compile + link + publish to firmware/ (never changes the version)
├── build-test.sh / .bat            # Non-versioning build/compile check
└── README.md
```
