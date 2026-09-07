// =============================================================================
// URTC-VISION-TOOL Firmware - Minimal host-side test harness: test_runner.h
// Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
// GPL-3.0 - see LICENSE
// =============================================================================
// No external test framework dependency, on purpose - same convention as
// sibling repo URTC-SMART-RACK's own tests/test_runner.h: these tests
// compile and run with the *host's* plain gcc/cc, never
// arm-none-eabi-gcc, since they exercise pure logic (sensor_frame.c,
// sensor_reading.c, rate_limiter.c, sensor_diagnostics.c), not anything
// that touches real MCU registers.
#ifndef TEST_RUNNER_H
#define TEST_RUNNER_H

#include <stdio.h>

#define TEST_ASSERT(cond, msg) \
    do { \
        if (!(cond)) { \
            printf("  FAIL: %s (%s:%d)\n", (msg), __FILE__, __LINE__); \
            (*failures)++; \
        } \
    } while (0)

void run_sensor_frame_tests(int *failures);
void run_sensor_reading_tests(int *failures);
void run_rate_limiter_tests(int *failures);
void run_sensor_diagnostics_tests(int *failures);
void run_vision_sensor_scenario_tests(int *failures);

#endif // TEST_RUNNER_H
