// =============================================================================
// URTC-VISION-TOOL Firmware - Interrupt-safe receive path: sensor_rx.c
// Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
// GPL-3.0-or-later - see LICENSE
// =============================================================================
#include "sensor_rx.h"
#include "urtc_frame.h"
#include "vision_sensor_link.h"
#include <stddef.h>

static const urtc_frame_format_t SENSOR_FORMAT = {SENSOR_FRAME_SOF, SENSOR_FRAME_VERSION, 8u, SENSOR_FRAME_MAX_PAYLOAD};

void sensor_rx_init(sensor_rx_t *rx)
{
    if (rx == NULL) {
        return;
    }
    (void)urtc_ring_init(&rx->ring, rx->ring_storage, SENSOR_RX_RING_SIZE);
    rx->count = 0u;
    rx->last_byte_ms = 0u;
    rx->overflow_bytes = 0u;
    rx->timeouts = 0u;
}

bool sensor_rx_on_byte(sensor_rx_t *rx, uint8_t byte)
{
    if (rx == NULL) {
        return false;
    }
    return urtc_ring_put(&rx->ring, byte);
}

// Throws away the first byte of the candidate and keeps the rest (the next start byte may already be inside it).
static void drop_first_byte(sensor_rx_t *rx)
{
    for (uint8_t i = 1u; i < rx->count; i++) {
        rx->frame[i - 1u] = rx->frame[i];
    }
    rx->count--;
}

// Drops leading bytes until the candidate starts with the start byte (or is empty).
static void skip_to_start(sensor_rx_t *rx)
{
    while (rx->count > 0u && rx->frame[0] != SENSOR_FRAME_SOF) {
        drop_first_byte(rx);
    }
}

bool sensor_rx_poll(sensor_rx_t *rx, rate_limiter_t *rl, sensor_freshness_t *fresh, sensor_diagnostics_t *diag, uint32_t now_ms, sensor_thermal_reading_t *out_reading)
{
    if (rx == NULL || rl == NULL || fresh == NULL || diag == NULL || out_reading == NULL) {
        return false;
    }
    rx->overflow_bytes += urtc_ring_take_dropped(&rx->ring);
    if (rx->count > 0u && (uint32_t)(now_ms - rx->last_byte_ms) > SENSOR_RX_BYTE_TIMEOUT_MS) {
        sensor_diagnostics_note_frame_error(diag);          // a half frame that never finished
        rx->timeouts++;
        rx->count = 0u;
    }
    uint8_t byte;
    while (urtc_ring_get(&rx->ring, &byte)) {
        rx->last_byte_ms = now_ms;
        if (rx->count == 0u && byte != SENSOR_FRAME_SOF) {
            continue;                                       // noise between frames: not a frame, not worth a count
        }
        rx->frame[rx->count++] = byte;
        for (;;) {
            uint8_t total = 0u;
            const urtc_frame_status_t status = urtc_frame_validate(&SENSOR_FORMAT, rx->frame, rx->count, &total);
            if (status == URTC_FRAME_INCOMPLETE) {
                break;                                      // keep buffering
            }
            if (status == URTC_FRAME_OK) {
                sensor_thermal_reading_t reading;
                const bool accepted = vision_sensor_link_process_frame(rl, fresh, diag, rx->frame, total, now_ms, &reading);
                rx->count = 0u;
                if (accepted) {
                    *out_reading = reading;
                    return true;
                }
                break;
            }
            // A damaged candidate: record it, resynchronise on the next start byte inside what was read.
            sensor_diagnostics_note_frame_error(diag);
            drop_first_byte(rx);
            skip_to_start(rx);
            if (rx->count == 0u) {
                break;
            }
        }
    }
    return false;
}
