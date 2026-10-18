// =============================================================================
// URTC-VISION-TOOL Firmware - tests for sensor_freshness.c
// Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
// GPL-3.0 - see LICENSE
// =============================================================================
#include "test_runner.h"
#include "../src/sensor_freshness.h"

void run_sensor_freshness_tests(int *failures)
{
    sensor_freshness_t f;
    sensor_freshness_init(&f);

    TEST_ASSERT(sensor_freshness_check(&f, 0, 0) == SENSOR_FRESH, "the first frame is fresh whatever its numbers");
    TEST_ASSERT(sensor_freshness_check(&f, 200, 123456) == SENSOR_FRESH, "the first frame is fresh with any sequence and timestamp");

    sensor_freshness_commit(&f, 10, 1000);
    TEST_ASSERT(sensor_freshness_check(&f, 11, 1010) == SENSOR_FRESH, "the next sequence and a later timestamp are fresh");
    TEST_ASSERT(sensor_freshness_check(&f, 10, 1010) == SENSOR_REPLAYED, "the same sequence is a replay");
    TEST_ASSERT(sensor_freshness_check(&f, 9, 1010) == SENSOR_REPLAYED, "an older sequence is a replay");
    TEST_ASSERT(sensor_freshness_check(&f, 11, 1000) == SENSOR_STALE, "a newer sequence over the same timestamp is stale");
    TEST_ASSERT(sensor_freshness_check(&f, 11, 999) == SENSOR_STALE, "a newer sequence over an older timestamp is stale");
    TEST_ASSERT(sensor_freshness_check(&f, 10, 1000) == SENSOR_REPLAYED, "the exact same frame is a replay, judged by its sequence first");

    // Checking never changes the baseline.
    TEST_ASSERT(sensor_freshness_check(&f, 11, 1010) == SENSOR_FRESH, "a check leaves the baseline alone");

    sensor_freshness_commit(&f, 11, 1010);
    TEST_ASSERT(sensor_freshness_check(&f, 11, 1020) == SENSOR_REPLAYED, "after committing, the committed sequence is a replay");

    sensor_freshness_reset(&f);
    TEST_ASSERT(sensor_freshness_check(&f, 1, 1) == SENSOR_FRESH, "after a reset any frame is fresh again");
}
