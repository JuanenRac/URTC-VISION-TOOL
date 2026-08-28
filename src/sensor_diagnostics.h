// =============================================================================
// URTC-VISION-TOOL Firmware - Sensor field diagnostics: sensor_diagnostics.h
// Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
// GPL-3.0 - see LICENSE
// =============================================================================
// Real, dedicated field-support counters - the promotion audit's own
// "separar diagnostico de salida de control y mantener contadores de
// error, latencia y reinicio de bus". This module never makes an
// accept/reject decision itself - sensor_frame.c/sensor_reading.c/
// rate_limiter.c do that; this only records what they decided, so a
// diagnostics bug can never accidentally influence which frames get
// accepted.
#ifndef SENSOR_DIAGNOSTICS_H
#define SENSOR_DIAGNOSTICS_H

#include <stdbool.h>
#include <stdint.h>

typedef struct {
    uint32_t frame_errors;       // sensor_frame_parse() rejections (bad SOF/version/length/CRC/incomplete)
    uint32_t out_of_range_count; // sensor_reading_validate_*() rejections
    uint32_t rate_limited_count; // rate_limiter_allow() rejections
    uint32_t disconnect_count;   // explicit "sensor went silent" events
    uint32_t bus_reset_count;
    uint32_t last_latency_ms;    // real time between the two most recent accepted frames
    bool has_last_accept_ms;
    uint32_t last_accept_ms;
} sensor_diagnostics_t;

void sensor_diagnostics_init(sensor_diagnostics_t *diag);
void sensor_diagnostics_note_frame_error(sensor_diagnostics_t *diag);
void sensor_diagnostics_note_out_of_range(sensor_diagnostics_t *diag);
void sensor_diagnostics_note_rate_limited(sensor_diagnostics_t *diag);
void sensor_diagnostics_note_disconnect(sensor_diagnostics_t *diag);
void sensor_diagnostics_note_bus_reset(sensor_diagnostics_t *diag);

// Records a real accepted frame at `now_ms`, updating `last_latency_ms`
// against the previous accepted frame's own time (0 on the very first
// accepted frame - there's nothing real to measure latency against yet).
void sensor_diagnostics_note_accepted_frame(sensor_diagnostics_t *diag, uint32_t now_ms);

#endif // SENSOR_DIAGNOSTICS_H
