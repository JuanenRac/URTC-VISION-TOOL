# Contributing to URTC-VISION-TOOL 🦾

We welcome contributions to the integrated visual and thermal perception toolhead of the HYDRA-UMC ecosystem.

## Technology Stack
- **Language**: C11 (Firmware), Python (Processing).
- **Hardware**: STM32F303 / G474, USB 3.0 UVC Camera.
- **Sensors**: MLX90640 Thermal Array (32x24), RGB Global Shutter.
- **Protocols**: CAN / FDCAN, I2C, UVC.

## Guidelines
1. **Calibration Accuracy**: Any changes to the thermal-to-RGB alignment logic must be validated against a physical calibration target with known heat signatures.
2. **Deterministic Sampling**: The I2C thermal sensor readout must not block the real-time CAN telemetry stack.
3. **Optics Integrity**: Ensure that 3D-printed enclosure modifications do not obscure the field of view (FOV) of either sensor.
4. **Testing**: Validate multi-modal fusion performance using the `VISION-NODE` integration tests.
