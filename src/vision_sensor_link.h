// =============================================================================
// URTC-VISION-TOOL Firmware - Real receive-path decision: vision_sensor_link.h
// Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
// GPL-3.0-or-later - see LICENSE
// =============================================================================
// The real dispatch chaining sensor-frame / sensor id / reading validation /
// freshness / rate limiting / diagnostics together, as a src/ module that the
// real MLX9064x receive path can call the day the PCB exists (see main.c's own
// note - none of MLX9064x/RGB trigger/PCB exist for this board yet). The tests
// call INTO this module.
//
// Order of the checks, and why: a frame is parsed (framing and CRC), its sensor
// is looked at (only the thermal camera is read on this link), its content is
// validated, it is judged against the last accepted frame of that sensor
// (sequence and timestamp), and only then is the rate limiter spent. A frame
// that is refused earlier never uses up the rate window of the good frame that
// follows it, and never moves the freshness baseline.
//
// Execution context: the state passed in is plain memory. Call every function
// of this module from ONE context - the main loop. A receive interrupt should
// only copy the received bytes into a ring buffer (single producer, volatile
// indices, a barrier before publishing the index); calling this from an
// interrupt while the main loop reads the diagnostics gives inconsistent
// snapshots.
#ifndef VISION_SENSOR_LINK_H
#define VISION_SENSOR_LINK_H

#include <stdbool.h>
#include <stdint.h>

#include "rate_limiter.h"
#include "sensor_diagnostics.h"
#include "sensor_freshness.h"
#include "sensor_reading.h"

// The real decision one receive attempt makes: a real, in-range, fresh thermal
// reading on success (written to `out_reading`, only ever on success), or
// nothing at all (with the real reason recorded in `diag`) on any failure -
// framing, sensor id, payload size, range, freshness or rate. `buf == NULL`
// models a real disconnection: no frame arrived in the expected window at all.
// `rl`, `fresh` and `diag` are mutated exactly as a real receive handler's own
// state would be - callers share one of each across every call. A missing `rl`,
// `fresh` or `diag` makes the call refuse (fail closed).
bool vision_sensor_link_process_frame(
    rate_limiter_t *rl,
    sensor_freshness_t *fresh,
    sensor_diagnostics_t *diag,
    const uint8_t *buf,
    uint8_t buf_len,
    uint32_t now_ms,
    sensor_thermal_reading_t *out_reading);

// One pass of the main loop: reports a link that has delivered no accepted
// frame for `silence_timeout_ms` (counted once per silence in the diagnostics)
// and forgets the freshness baseline then, because a sensor that went quiet may
// come back with its counters restarted. Returns true when it reports a new
// silence.
bool vision_sensor_link_tick(
    sensor_freshness_t *fresh,
    sensor_diagnostics_t *diag,
    uint32_t now_ms,
    uint32_t silence_timeout_ms);

#endif // VISION_SENSOR_LINK_H
