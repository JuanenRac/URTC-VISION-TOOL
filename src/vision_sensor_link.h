// =============================================================================
// URTC-VISION-TOOL Firmware - Real receive-path decision: vision_sensor_link.h
// Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
// GPL-3.0 - see LICENSE
// =============================================================================
// Found while auditing the code: the real
// dispatch chaining sensor-frame/reading/rate-limiter/diagnostics
// together existed only as a static function inside this repo's own
// tests/test_vision_sensor_scenarios.c, not as a real src/ module
// anything else could call. Promoted here so the real MLX9064x receive
// path is ready to wire into a real I2C/SPI ISR the day the PCB exists
// (see main.c's own note - none of MLX9064x/RGB trigger/PCB exist for
// this board yet) - the tests now call INTO this module instead of
// defining their own private copy of the logic under test.
#ifndef VISION_SENSOR_LINK_H
#define VISION_SENSOR_LINK_H

#include <stdbool.h>
#include <stdint.h>

#include "rate_limiter.h"
#include "sensor_diagnostics.h"
#include "sensor_reading.h"

// The real decision one receive attempt makes: a real, in-range thermal
// reading on success (written to `out_reading`, only ever on success),
// or nothing at all (with the real reason recorded in `diag`) on any
// failure - framing, rate limiting, or range validation. `buf == NULL`
// models a real disconnection: no frame arrived in the expected window
// at all. `rl`/`diag` are mutated exactly as a real receive interrupt
// handler's own rate-limiter/diagnostics state would be - callers share
// one of each across every real call the same way a real ISR would.
bool vision_sensor_link_process_frame(
    rate_limiter_t *rl,
    sensor_diagnostics_t *diag,
    const uint8_t *buf,
    uint8_t buf_len,
    uint32_t now_ms,
    sensor_thermal_reading_t *out_reading);

#endif // VISION_SENSOR_LINK_H
