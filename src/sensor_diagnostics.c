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
    diag->rate_limited_count = 0;
    diag->disconnect_count = 0;
    diag->bus_reset_count = 0;
    diag->last_latency_ms = 0;
    diag->has_last_accept_ms = false;
    diag->last_accept_ms = 0;
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

void sensor_diagnostics_note_rate_limited(sensor_diagnostics_t *diag)
{
    if (diag == NULL) return;
    diag->rate_limited_count++;
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
        diag->last_latency_ms = now_ms - diag->last_accept_ms; // real, wraps correctly
    } else {
        diag->last_latency_ms = 0;
    }
    diag->last_accept_ms = now_ms;
    diag->has_last_accept_ms = true;
}
