// =============================================================================
// URTC-VISION-TOOL Firmware - Sensor field diagnostics: sensor_diagnostics.c
// Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
// GPL-3.0 - see LICENSE
// =============================================================================
#include "sensor_diagnostics.h"
#include <stddef.h>

void sensor_diagnostics_init(sensor_diagnostics_t *diag)
{
    if (diag == NULL) {
        return;
    }
    diag->frame_errors = 0;
    diag->out_of_range_count = 0;
    diag->malformed_payload_count = 0;
    diag->rate_limited_count = 0;
    diag->unsupported_sensor_count = 0;
    diag->replay_count = 0;
    diag->stale_count = 0;
    diag->disconnect_count = 0;
    diag->bus_reset_count = 0;
    diag->last_interarrival_ms = 0;
    diag->last_sensor_latency_ms = 0;
    diag->has_last_accept_ms = false;
    diag->last_accept_ms = 0;
    diag->silent = false;
}

void sensor_diagnostics_note_frame_error(sensor_diagnostics_t *diag)
{
    if (diag == NULL) return;
    diag->frame_errors++;
}

void sensor_diagnostics_note_out_of_range(sensor_diagnostics_t *diag)
{
    if (diag == NULL) return;
    diag->out_of_range_count++;
}

void sensor_diagnostics_note_malformed_payload(sensor_diagnostics_t *diag)
{
    if (diag == NULL) return;
    diag->malformed_payload_count++;
}

void sensor_diagnostics_note_rate_limited(sensor_diagnostics_t *diag)
{
    if (diag == NULL) return;
    diag->rate_limited_count++;
}

void sensor_diagnostics_note_unsupported_sensor(sensor_diagnostics_t *diag)
{
    if (diag == NULL) return;
    diag->unsupported_sensor_count++;
}

void sensor_diagnostics_note_replay(sensor_diagnostics_t *diag)
{
    if (diag == NULL) return;
    diag->replay_count++;
}

void sensor_diagnostics_note_stale(sensor_diagnostics_t *diag)
{
    if (diag == NULL) return;
    diag->stale_count++;
}

void sensor_diagnostics_note_disconnect(sensor_diagnostics_t *diag)
{
    if (diag == NULL) return;
    diag->disconnect_count++;
}

void sensor_diagnostics_note_bus_reset(sensor_diagnostics_t *diag)
{
    if (diag == NULL) return;
    diag->bus_reset_count++;
}

void sensor_diagnostics_note_accepted_frame(sensor_diagnostics_t *diag, uint32_t now_ms)
{
    if (diag == NULL) return;
    if (diag->has_last_accept_ms) {
        diag->last_interarrival_ms = now_ms - diag->last_accept_ms; // real, wraps correctly
    } else {
        diag->last_interarrival_ms = 0;
    }
    diag->last_accept_ms = now_ms;
    diag->has_last_accept_ms = true;
    diag->silent = false;
}

void sensor_diagnostics_note_sensor_latency(sensor_diagnostics_t *diag, uint32_t now_ms, uint32_t sensor_timestamp_ms)
{
    if (diag == NULL) return;
    diag->last_sensor_latency_ms = now_ms - sensor_timestamp_ms; // wraps correctly
}

bool sensor_diagnostics_check_silence(sensor_diagnostics_t *diag, uint32_t now_ms, uint32_t timeout_ms)
{
    if (diag == NULL || !diag->has_last_accept_ms || diag->silent) {
        return false;
    }
    if ((now_ms - diag->last_accept_ms) < timeout_ms) {
        return false;
    }
    diag->silent = true;
    diag->disconnect_count++;
    return true;
}
