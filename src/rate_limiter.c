// =============================================================================
// URTC-VISION-TOOL Firmware - Sensor frame rate limiting: rate_limiter.c
// Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
// GPL-3.0 - see LICENSE
// =============================================================================
#include "rate_limiter.h"
#include <stddef.h>

void rate_limiter_init(rate_limiter_t *rl, uint32_t min_interval_ms)
{
    if (rl == NULL) {
        return;
    }
    rl->min_interval_ms = min_interval_ms;
    rl->last_accept_ms = 0;
    rl->has_accepted_any = false;
}

bool rate_limiter_allow(rate_limiter_t *rl, uint32_t now_ms)
{
    if (rl == NULL) {
        return false; // fail closed: no real limiter state at all never allows
    }
    if (!rl->has_accepted_any) {
        rl->last_accept_ms = now_ms;
        rl->has_accepted_any = true;
        return true;
    }
    // Unsigned subtraction wraps correctly even across a real uint32_t
    // millisecond-counter rollover.
    if ((now_ms - rl->last_accept_ms) < rl->min_interval_ms) {
        return false;
    }
    rl->last_accept_ms = now_ms;
    return true;
}
