// =============================================================================
// URTC-VISION-TOOL Firmware - Frame freshness: sensor_freshness.h
// Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
// GPL-3.0 - see LICENSE
// =============================================================================
// A frame carries a sequence number and a sensor-side timestamp. Without a
// check on them, a frame repeated verbatim, an old frame that arrives late, or
// a sensor that keeps re-sending its last buffer (a typical I2C/DMA failure)
// looks like a healthy stream. This module judges one frame against the last
// ACCEPTED one of the same sensor:
//
//   - the sequence number must be newer (8-bit wrap-around aware: a step of
//     1..127 forward is newer, anything else is a repeat or an older frame);
//   - the timestamp must have advanced (32-bit wrap-around aware).
//
// Checking and committing are separate calls, so a frame that is refused for
// any other reason (out of range, too fast) never moves the baseline.
// Pure logic against caller-supplied values: no clock, no hardware.
#ifndef SENSOR_FRESHNESS_H
#define SENSOR_FRESHNESS_H

#include <stdbool.h>
#include <stdint.h>

typedef struct {
    bool has_last;
    uint8_t last_seq;
    uint32_t last_timestamp_ms;
} sensor_freshness_t;

typedef enum {
    SENSOR_FRESH = 0,       // newer than the last accepted frame (or the first one)
    SENSOR_REPLAYED,        // the sequence number is not newer: a repeat, or an older frame arriving late
    SENSOR_STALE,           // the sequence advanced but the sensor timestamp did not: a sensor re-sending frozen data
} sensor_freshness_status_t;

void sensor_freshness_init(sensor_freshness_t *f);

// Judges a frame without changing anything. A missing state counts as REPLAYED
// (fail closed).
sensor_freshness_status_t sensor_freshness_check(const sensor_freshness_t *f, uint8_t seq, uint32_t timestamp_ms);

// Makes this frame the new baseline. Call it only for a frame that was accepted.
void sensor_freshness_commit(sensor_freshness_t *f, uint8_t seq, uint32_t timestamp_ms);

// Forgets the baseline - the next frame is accepted whatever its numbers. Use
// it when a sensor may have restarted its counters (after a long silence, a
// bus reset).
void sensor_freshness_reset(sensor_freshness_t *f);

#endif // SENSOR_FRESHNESS_H
