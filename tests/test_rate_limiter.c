// =============================================================================
// URTC-VISION-TOOL Firmware - tests for rate_limiter.c
// Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
// GPL-3.0 - see LICENSE
// =============================================================================
#include "test_runner.h"
#include "../src/rate_limiter.h"

void run_rate_limiter_tests(int *failures)
{
    // --- Real first frame is always allowed ---
    {
        rate_limiter_t rl;
        rate_limiter_init(&rl, 100);
        TEST_ASSERT(rate_limiter_allow(&rl, 0) == true, "the very first frame is always allowed, regardless of the configured interval");
    }

    // --- Real throttling of a too-fast follow-up frame ---
    {
        rate_limiter_t rl;
        rate_limiter_init(&rl, 100);
        rate_limiter_allow(&rl, 0);
        TEST_ASSERT(rate_limiter_allow(&rl, 50) == false, "a frame 50ms after the last accepted one, with a 100ms minimum interval, is throttled");
    }

    // --- Real boundary: exactly at the minimum interval is allowed ---
    {
        rate_limiter_t rl;
        rate_limiter_init(&rl, 100);
        rate_limiter_allow(&rl, 0);
        TEST_ASSERT(rate_limiter_allow(&rl, 100) == true, "a frame exactly 100ms after the last accepted one is allowed");
    }

    // --- Real sustained flood: only frames spaced far enough apart are accepted ---
    {
        rate_limiter_t rl;
        rate_limiter_init(&rl, 100);
        int accepted = 0;
        for (uint32_t t = 0; t <= 500; t += 10) {
            if (rate_limiter_allow(&rl, t)) {
                accepted++;
            }
        }
        // t=0,100,200,300,400,500 are the only real acceptable instants at 10ms granularity -> 6.
        TEST_ASSERT(accepted == 6, "a real 10ms-interval flood against a 100ms limiter accepts exactly the 6 real 100ms-spaced frames");
    }

    // --- Real recovery: throttling stops once enough time has passed ---
    {
        rate_limiter_t rl;
        rate_limiter_init(&rl, 100);
        rate_limiter_allow(&rl, 0);
        TEST_ASSERT(rate_limiter_allow(&rl, 50) == false, "throttled at 50ms");
        TEST_ASSERT(rate_limiter_allow(&rl, 150) == true, "the same limiter allows a real frame once 100ms have passed since the last ACCEPTED frame (not since the throttled one)");
    }
}
