# Contributing to URTC-VISION-TOOL 🦾

We welcome contributions to the integrated visual and thermal perception toolhead of the URTC ecosystem.

## Technology Stack
- **Language**: C11 (firmware), Python 3.10+ (the `vision_companion` package, with numpy and Pillow).
- **Planned hardware (not confirmed)**: a Cortex-M4F STM32 (the exact part is undecided, because no PCB or schematic exists yet), a USB RGB camera, an MLX9064x thermal array (32x24 for the MLX90640 and MLX90642, 16x12 for the MLX90641) and a CAN link.
- **What exists today**: pure C logic tested on a PC (sensor frame, reading checks, freshness, rate limiting, diagnostics) and a Python companion that runs on synthetic frames. Nothing has run against a real sensor, camera or board.

## Guidelines
1. **Calibration Accuracy**: Any changes to the thermal-to-RGB alignment logic must be validated against a physical calibration target with known heat signatures once such a target and cameras exist. Until then the alignment assumes a shared field of view and is tested on synthetic frames.
2. **Deterministic Sampling**: The I2C thermal sensor readout must not block the real-time CAN telemetry stack (a design goal for the future drivers; there are none yet).
3. **Optics Integrity**: Ensure that 3D-printed enclosure modifications do not obscure the field of view (FOV) of either sensor.
4. **Testing**: every change to `src/*.c` comes with host tests in `tests/`, and every change to `src/vision_companion/` with pytest cases; the two build scripts list the same sources (a test checks it). Multi-modal fusion tests with the `VISION-NODE` project are planned and do not exist yet.
