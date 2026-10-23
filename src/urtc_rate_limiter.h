// =============================================================================
// URTC-COMMON - firmware_base/urtc_rate_limiter.h
// Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
// GPL-3.0-or-later - see LICENSE
// =============================================================================
// The minimum interval between two accepted messages of a link: a sensor that floods the link is throttled, not
// trusted at whatever rate it happens to send. Pure logic against a millisecond clock the caller passes in, so it
// is tested on the host with no hardware. The vision sensor link uses it; the shared vectors (`rate_vectors.h`)
// hold every user to the same decisions, the wrap of the 32-bit millisecond counter included.
//
// Copied with `python tools/vendor_copy.py sync TARGET --set firmware_frame`. Header only.
#ifndef URTC_RATE_LIMITER_H
#define URTC_RATE_LIMITER_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

typedef struct {
    uint32_t min_interval_ms;
    uint32_t last_accept_ms;
    bool has_accepted_any;
} urtc_rate_limiter_t;

static inline void urtc_rate_limiter_init(urtc_rate_limiter_t *limiter, uint32_t min_interval_ms)
{
    if (limiter == NULL) {
        return;
    }
    limiter->min_interval_ms = min_interval_ms;
    limiter->last_accept_ms = 0;
    limiter->has_accepted_any = false;
}

// True (and `now_ms` becomes the time of the last accepted message) when none was accepted before or at least
// `min_interval_ms` has passed since the last one; false means "throttled": the caller must not process the message
// anyway. A missing limiter never allows (fail closed). Unsigned subtraction keeps the decision right across the
// wrap of the millisecond counter.
static inline bool urtc_rate_limiter_allow(urtc_rate_limiter_t *limiter, uint32_t now_ms)
{
    if (limiter == NULL) {
        return false;
    }
    if (!limiter->has_accepted_any) {
        limiter->last_accept_ms = now_ms;
        limiter->has_accepted_any = true;
        return true;
    }
    if ((uint32_t)(now_ms - limiter->last_accept_ms) < limiter->min_interval_ms) {
        return false;
    }
    limiter->last_accept_ms = now_ms;
    return true;
}

#endif // URTC_RATE_LIMITER_H
