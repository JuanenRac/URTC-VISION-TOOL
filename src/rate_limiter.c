// =============================================================================
// URTC-VISION-TOOL Firmware - Sensor frame rate limiting: rate_limiter.c
// Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
// GPL-3.0-or-later - see LICENSE
// =============================================================================
#include "rate_limiter.h"

void rate_limiter_init(rate_limiter_t *rl, uint32_t min_interval_ms)
{
    urtc_rate_limiter_init(rl, min_interval_ms);
}

bool rate_limiter_allow(rate_limiter_t *rl, uint32_t now_ms)
{
    return urtc_rate_limiter_allow(rl, now_ms);
}
