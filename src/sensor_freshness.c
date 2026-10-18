// =============================================================================
// URTC-VISION-TOOL Firmware - Frame freshness: sensor_freshness.c
// Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
// GPL-3.0 - see LICENSE
// =============================================================================
#include "sensor_freshness.h"
#include <stddef.h>

void sensor_freshness_init(sensor_freshness_t *f)
{
    if (f == NULL) {
        return;
    }
    f->has_last = false;
    f->last_seq = 0;
    f->last_timestamp_ms = 0;
}

sensor_freshness_status_t sensor_freshness_check(const sensor_freshness_t *f, uint8_t seq, uint32_t timestamp_ms)
{
    if (f == NULL) {
        return SENSOR_REPLAYED;
    }
    if (!f->has_last) {
        return SENSOR_FRESH;
    }
    // The 8-bit sequence space is read as a signed ring: a step of 1..127 is
    // forward progress (255 -> 0 included), 0 is a repeat, and a step of 128 or
    // more reads as going backwards.
    const int8_t seq_step = (int8_t)(uint8_t)(seq - f->last_seq);
    if (seq_step <= 0) {
        return SENSOR_REPLAYED;
    }
    // Same for the 32-bit millisecond timestamp, so a counter wrap is not a stall.
    const int32_t time_step = (int32_t)(uint32_t)(timestamp_ms - f->last_timestamp_ms);
    if (time_step <= 0) {
        return SENSOR_STALE;
    }
    return SENSOR_FRESH;
}

void sensor_freshness_commit(sensor_freshness_t *f, uint8_t seq, uint32_t timestamp_ms)
{
    if (f == NULL) {
        return;
    }
    f->has_last = true;
    f->last_seq = seq;
    f->last_timestamp_ms = timestamp_ms;
}

void sensor_freshness_reset(sensor_freshness_t *f)
{
    sensor_freshness_init(f);
}
