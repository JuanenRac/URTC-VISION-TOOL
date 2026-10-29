// =============================================================================
// URTC-VISION-TOOL Firmware - Interrupt-safe receive path: sensor_rx.h
// Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
// GPL-3.0-or-later - see LICENSE
// =============================================================================
// The shape the receive path takes once the sensor link has an interrupt: the interrupt (or the DMA handler)
// calls ONLY sensor_rx_on_byte(), which puts the byte in a single-producer ring (urtc_ring.h); the main loop calls
// sensor_rx_poll(), which takes the bytes out, finds the frames in them (resynchronising on a start byte, dropping a
// half frame that waited longer than the inter-byte timeout) and hands each complete frame to
// vision_sensor_link_process_frame(). So the rate limiter, the freshness state and the diagnostics are touched from
// ONE context and a reader of the diagnostics never sees a half-updated snapshot.
//
// No interrupt exists yet (no board, no transport): the host tests play the bytes of the scenarios through it.
#ifndef SENSOR_RX_H
#define SENSOR_RX_H

#include <stdbool.h>
#include <stdint.h>

#include "rate_limiter.h"
#include "sensor_diagnostics.h"
#include "sensor_frame.h"
#include "sensor_freshness.h"
#include "sensor_reading.h"
#include "urtc_ring.h"

#define SENSOR_RX_RING_SIZE 64u                 // a power of two; holds two whole frames
#define SENSOR_RX_BYTE_TIMEOUT_MS 20u           // a half frame that waited this long is dropped

typedef struct {
    urtc_ring_t ring;
    uint8_t ring_storage[SENSOR_RX_RING_SIZE];
    uint8_t frame[SENSOR_FRAME_MAX_SIZE];       // the frame being assembled (main loop only)
    uint8_t count;
    uint32_t last_byte_ms;
    uint32_t overflow_bytes;                    // bytes the ring had no room for (they show up as a lost frame)
    uint32_t timeouts;                          // half frames dropped by the inter-byte timeout
} sensor_rx_t;

void sensor_rx_init(sensor_rx_t *rx);

// Interrupt side: the only call an interrupt may make. Returns false when the byte was dropped.
bool sensor_rx_on_byte(sensor_rx_t *rx, uint8_t byte);

// Main-loop side: drains the ring. Returns true as soon as one frame yielded an accepted reading (`out_reading` is
// written); call it again to continue with the bytes that are left. Returns false when the ring is empty.
// Every frame that is malformed is recorded in `diag` by vision_sensor_link_process_frame() or here (a damaged
// candidate) and never yields a reading.
bool sensor_rx_poll(sensor_rx_t *rx, rate_limiter_t *rl, sensor_freshness_t *fresh, sensor_diagnostics_t *diag, uint32_t now_ms, sensor_thermal_reading_t *out_reading);

#endif // SENSOR_RX_H
