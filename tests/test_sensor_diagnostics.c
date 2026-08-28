// =============================================================================
// URTC-VISION-TOOL Firmware - tests for sensor_diagnostics.c
// Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
// GPL-3.0 - see LICENSE
// =============================================================================
#include "test_runner.h"
#include "../src/sensor_diagnostics.h"

void run_sensor_diagnostics_tests(int *failures)
{
    // --- Real init starts every counter at zero ---
    {
        sensor_diagnostics_t diag;
        sensor_diagnostics_init(&diag);
        TEST_ASSERT(diag.frame_errors == 0, "frame_errors starts at 0");
        TEST_ASSERT(diag.out_of_range_count == 0, "out_of_range_count starts at 0");
        TEST_ASSERT(diag.rate_limited_count == 0, "rate_limited_count starts at 0");
        TEST_ASSERT(diag.disconnect_count == 0, "disconnect_count starts at 0");
        TEST_ASSERT(diag.bus_reset_count == 0, "bus_reset_count starts at 0");
        TEST_ASSERT(diag.has_last_accept_ms == false, "no accepted frame has been recorded yet");
    }

    // --- Real independent counters ---
    {
        sensor_diagnostics_t diag;
        sensor_diagnostics_init(&diag);
        sensor_diagnostics_note_frame_error(&diag);
        sensor_diagnostics_note_frame_error(&diag);
        sensor_diagnostics_note_out_of_range(&diag);
        sensor_diagnostics_note_rate_limited(&diag);
        sensor_diagnostics_note_disconnect(&diag);
        sensor_diagnostics_note_bus_reset(&diag);

        TEST_ASSERT(diag.frame_errors == 2, "two real frame errors are counted independently");
        TEST_ASSERT(diag.out_of_range_count == 1, "one real out-of-range reading is counted");
        TEST_ASSERT(diag.rate_limited_count == 1, "one real rate-limited frame is counted");
        TEST_ASSERT(diag.disconnect_count == 1, "one real disconnect event is counted");
        TEST_ASSERT(diag.bus_reset_count == 1, "one real bus reset is counted");
    }

    // --- Real latency tracking ---
    {
        sensor_diagnostics_t diag;
        sensor_diagnostics_init(&diag);
        sensor_diagnostics_note_accepted_frame(&diag, 1000);
        TEST_ASSERT(diag.last_latency_ms == 0, "the very first accepted frame has no real prior frame to measure latency against");

        sensor_diagnostics_note_accepted_frame(&diag, 1250);
        TEST_ASSERT(diag.last_latency_ms == 250, "the real latency between two accepted frames is tracked correctly");

        sensor_diagnostics_note_accepted_frame(&diag, 1400);
        TEST_ASSERT(diag.last_latency_ms == 150, "a real subsequent accepted frame updates the latency again");
    }
}
