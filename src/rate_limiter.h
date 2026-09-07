// =============================================================================
// URTC-VISION-TOOL Firmware - Sensor frame rate limiting: rate_limiter.h
// Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
// GPL-3.0 - see LICENSE
// =============================================================================
// Real minimum-interval enforcement between accepted sensor frames - the
// promotion audit's own "limites de tasa para que el firmware no acepte
// entradas ambiguas": a malfunctioning or flooding sensor sending frames
// faster than physically expected must be throttled, not trusted at
// whatever rate it happens to arrive. Pure logic against a caller-supplied
// millisecond clock - real and testable on the host without real hardware.
#ifndef RATE_LIMITER_H
#define RATE_LIMITER_H

#include <stdbool.h>
#include <stdint.h>

typedef struct {
    uint32_t min_interval_ms;
    uint32_t last_accept_ms;
    bool has_accepted_any;
} rate_limiter_t;

void rate_limiter_init(rate_limiter_t *rl, uint32_t min_interval_ms);

// Real accept/reject decision for a frame arriving at `now_ms`: true (and
// records `now_ms` as the new last-accepted time) once at least
// `min_interval_ms` has really passed since the last accepted frame, or
// if none has ever been accepted; false otherwise - the caller must treat
// false as "throttled", not silently process the frame anyway.
bool rate_limiter_allow(rate_limiter_t *rl, uint32_t now_ms);

#endif // RATE_LIMITER_H
