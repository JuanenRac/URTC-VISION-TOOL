// =============================================================================
// URTC-VISION-TOOL Firmware - Robustness tests: test_robustness.c
// Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
// GPL-3.0-or-later - see LICENSE
// =============================================================================
// What the logic does with input that should never arrive: missing state
// (a null pointer fails closed, it never lets a frame through), every
// truncation of a valid frame, every single-bit corruption of it, encode /
// parse round trips for every payload length, the exact edges of the
// accepted temperature range, and the millisecond counter wrapping around.
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#include "../src/rate_limiter.h"
#include "../src/sensor_diagnostics.h"
#include "../src/sensor_freshness.h"
#include "../src/sensor_frame.h"
#include "../src/sensor_reading.h"
#include "../src/vision_sensor_link.h"
#include "test_runner.h"

static void null_guards(int *failures)
{
    rate_limiter_init(NULL, 100);
    TEST_ASSERT(rate_limiter_allow(NULL, 0) == false, "a missing limiter never allows a frame (fails closed)");

    sensor_diagnostics_init(NULL);
    sensor_diagnostics_note_frame_error(NULL);
    sensor_diagnostics_note_out_of_range(NULL);
    sensor_diagnostics_note_rate_limited(NULL);
    sensor_diagnostics_note_unsupported_sensor(NULL);
    sensor_diagnostics_note_disconnect(NULL);
    sensor_diagnostics_note_bus_reset(NULL);
    sensor_diagnostics_note_accepted_frame(NULL, 5);
    sensor_diagnostics_note_malformed_payload(NULL);
    sensor_diagnostics_note_replay(NULL);
    sensor_diagnostics_note_stale(NULL);
    sensor_diagnostics_note_sensor_latency(NULL, 5, 1);
    TEST_ASSERT(sensor_diagnostics_check_silence(NULL, 5, 1) == false, "a missing diagnostics state reports no silence");
    sensor_freshness_init(NULL);
    sensor_freshness_commit(NULL, 1, 1);
    sensor_freshness_reset(NULL);
    TEST_ASSERT(sensor_freshness_check(NULL, 1, 1) == SENSOR_REPLAYED, "a missing freshness state fails closed");
    TEST_ASSERT(1, "diagnostics calls with a null state do nothing and do not crash");

    sensor_frame_t frame;
    uint8_t buf[SENSOR_FRAME_MAX_SIZE];
    TEST_ASSERT(sensor_frame_parse(NULL, 10, &frame) == SENSOR_FRAME_ERR_INCOMPLETE, "parse of a null buffer is incomplete");
    TEST_ASSERT(sensor_frame_parse(buf, 10, NULL) == SENSOR_FRAME_ERR_INCOMPLETE, "parse into a null frame is incomplete");

    uint8_t payload[2] = { 0, 0 };
    TEST_ASSERT(sensor_frame_encode(1, 0, 0, payload, 2, NULL) == 0, "encode into a null buffer produces nothing");
    TEST_ASSERT(sensor_frame_encode(1, 0, 0, NULL, 2, buf) == 0, "encode of a payload that is not there produces nothing");
    TEST_ASSERT(sensor_frame_encode(1, 0, 0, payload, SENSOR_FRAME_MAX_PAYLOAD + 1, buf) == 0, "encode of an oversized payload produces nothing");
    TEST_ASSERT(sensor_frame_encode(1, 0, 0, NULL, 0, buf) == 10, "an empty frame needs no payload pointer and is ten bytes");

    sensor_thermal_reading_t reading;
    TEST_ASSERT(sensor_reading_validate_thermal(NULL, 2, &reading) == SENSOR_READING_ERR_WRONG_PAYLOAD_LEN, "a missing payload is not a reading");
    TEST_ASSERT(sensor_reading_validate_thermal(payload, 2, NULL) == SENSOR_READING_ERR_WRONG_PAYLOAD_LEN, "a missing output is refused");
}

static void truncation_and_corruption(int *failures)
{
    uint8_t payload[2] = { 0x03, 0xE8 }; // 10.00 degrees
    uint8_t buf[SENSOR_FRAME_MAX_SIZE];
    uint8_t n = sensor_frame_encode(SENSOR_ID_THERMAL, 7, 123456, payload, 2, buf);
    TEST_ASSERT(n == 12, "a thermal frame with a 2-byte payload is 12 bytes");

    sensor_frame_t frame;
    TEST_ASSERT(sensor_frame_parse(buf, n, &frame) == SENSOR_FRAME_OK, "the unmodified frame parses");
    TEST_ASSERT(frame.sensor_id == SENSOR_ID_THERMAL && frame.seq == 7 && frame.timestamp_ms == 123456 && frame.len == 2, "all header fields survive");

    int all_incomplete = 1;
    for (uint8_t cut = 0; cut < n; cut++) {
        if (sensor_frame_parse(buf, cut, &frame) != SENSOR_FRAME_ERR_INCOMPLETE) all_incomplete = 0;
    }
    TEST_ASSERT(all_incomplete, "every truncation of a valid frame is reported incomplete, never accepted");

    int all_detected = 1;
    for (uint8_t byte = 0; byte < n; byte++) {
        for (int bit = 0; bit < 8; bit++) {
            uint8_t damaged[SENSOR_FRAME_MAX_SIZE];
            memcpy(damaged, buf, n);
            damaged[byte] ^= (uint8_t)(1u << bit);
            if (sensor_frame_parse(damaged, n, &frame) == SENSOR_FRAME_OK) all_detected = 0;
        }
    }
    TEST_ASSERT(all_detected, "every single-bit corruption of the frame is rejected");

    uint8_t extra[SENSOR_FRAME_MAX_SIZE + 4];
    memcpy(extra, buf, n);
    memset(extra + n, 0xAA, 4);
    TEST_ASSERT(sensor_frame_parse(extra, (uint8_t)(n + 4), &frame) == SENSOR_FRAME_OK, "bytes after a complete frame are not part of it");

    uint8_t bad_len[SENSOR_FRAME_MAX_SIZE + 4];
    memcpy(bad_len, buf, n);
    bad_len[8] = SENSOR_FRAME_MAX_PAYLOAD + 1;
    TEST_ASSERT(sensor_frame_parse(bad_len, (uint8_t)(n + 4), &frame) == SENSOR_FRAME_ERR_LENGTH_OUT_OF_RANGE, "a declared payload longer than the maximum is rejected before reading it");
    bad_len[8] = 255;
    TEST_ASSERT(sensor_frame_parse(bad_len, (uint8_t)(n + 4), &frame) == SENSOR_FRAME_ERR_LENGTH_OUT_OF_RANGE, "a declared payload of 255 does not overflow the length arithmetic");
}

static void round_trips(int *failures)
{
    int ok = 1;
    for (uint8_t len = 0; len <= SENSOR_FRAME_MAX_PAYLOAD; len++) {
        uint8_t payload[SENSOR_FRAME_MAX_PAYLOAD];
        for (uint8_t i = 0; i < len; i++) payload[i] = (uint8_t)(0x30 + i * 7);
        uint8_t buf[SENSOR_FRAME_MAX_SIZE];
        uint8_t n = sensor_frame_encode(0x5A, (uint8_t)(len * 3), 0xDEADBEEFu, payload, len, buf);
        sensor_frame_t frame;
        if (n != 10u + len) ok = 0;
        if (sensor_frame_parse(buf, n, &frame) != SENSOR_FRAME_OK) { ok = 0; continue; }
        if (frame.len != len || frame.sensor_id != 0x5A || frame.seq != (uint8_t)(len * 3) || frame.timestamp_ms != 0xDEADBEEFu) ok = 0;
        if (memcmp(frame.payload, payload, len) != 0) ok = 0;
    }
    TEST_ASSERT(ok, "encode then parse returns the same frame for every payload length from 0 to the maximum");

    uint8_t buf[SENSOR_FRAME_MAX_SIZE] = { SENSOR_FRAME_SOF, SENSOR_FRAME_VERSION, 1, 0, 0, 0, 0, 0, 0, 0 };
    buf[9] = sensor_frame_crc8(buf, 9);
    sensor_frame_t frame;
    TEST_ASSERT(sensor_frame_parse(buf, 10, &frame) == SENSOR_FRAME_OK, "the smallest legal frame (no payload) parses");
    buf[0] = 0x00;
    TEST_ASSERT(sensor_frame_parse(buf, 10, &frame) == SENSOR_FRAME_ERR_BAD_SOF, "a wrong start byte is a bad SOF");
    buf[0] = SENSOR_FRAME_SOF;
    buf[1] = (uint8_t)(SENSOR_FRAME_VERSION + 1u);
    TEST_ASSERT(sensor_frame_parse(buf, 10, &frame) == SENSOR_FRAME_ERR_UNSUPPORTED_VERSION, "an unknown protocol version is refused before the CRC is looked at");
    buf[1] = 1;
    TEST_ASSERT(sensor_frame_parse(buf, 10, &frame) == SENSOR_FRAME_ERR_UNSUPPORTED_VERSION, "version 1, the little-endian layout, is refused instead of being read as other numbers");
}

static void reading_range_edges(int *failures)
{
    sensor_thermal_reading_t reading;
    struct { int16_t value; sensor_reading_status_t expect; const char *name; } cases[] = {
        { SENSOR_READING_MIN_TEMP_CENTIDEGREES_C, SENSOR_READING_OK, "the lowest accepted temperature" },
        { SENSOR_READING_MIN_TEMP_CENTIDEGREES_C - 1, SENSOR_READING_ERR_TEMP_OUT_OF_RANGE, "one step below the range" },
        { SENSOR_READING_MAX_TEMP_CENTIDEGREES_C, SENSOR_READING_OK, "the highest accepted temperature" },
        { SENSOR_READING_MAX_TEMP_CENTIDEGREES_C + 1, SENSOR_READING_ERR_TEMP_OUT_OF_RANGE, "one step above the range" },
        { 0, SENSOR_READING_OK, "zero degrees" },
        { INT16_MIN, SENSOR_READING_ERR_TEMP_OUT_OF_RANGE, "the most negative 16-bit value" },
        { INT16_MAX, SENSOR_READING_ERR_TEMP_OUT_OF_RANGE, "the most positive 16-bit value" },
    };
    for (unsigned i = 0; i < sizeof(cases) / sizeof(cases[0]); i++) {
        uint8_t payload[2] = { (uint8_t)((uint16_t)cases[i].value >> 8), (uint8_t)((uint16_t)cases[i].value & 0xFF) };
        sensor_reading_status_t got = sensor_reading_validate_thermal(payload, 2, &reading);
        TEST_ASSERT(got == cases[i].expect, cases[i].name);
        if (got == SENSOR_READING_OK) TEST_ASSERT(reading.temp_centidegrees_c == cases[i].value, "an accepted reading is returned as sent");
    }
    uint8_t one[1] = { 0 }, three[3] = { 0, 0, 0 };
    TEST_ASSERT(sensor_reading_validate_thermal(one, 1, &reading) == SENSOR_READING_ERR_WRONG_PAYLOAD_LEN, "a 1-byte payload is not a temperature");
    TEST_ASSERT(sensor_reading_validate_thermal(three, 3, &reading) == SENSOR_READING_ERR_WRONG_PAYLOAD_LEN, "a 3-byte payload is not a temperature");
    TEST_ASSERT(sensor_reading_validate_thermal(one, 0, &reading) == SENSOR_READING_ERR_WRONG_PAYLOAD_LEN, "an empty payload is not a temperature");
}

static void clock_wraparound(int *failures)
{
    rate_limiter_t rl;
    rate_limiter_init(&rl, 100);
    TEST_ASSERT(rate_limiter_allow(&rl, 0xFFFFFFF0u), "the first frame near the end of the counter is allowed");
    TEST_ASSERT(!rate_limiter_allow(&rl, 0xFFFFFFFFu), "15 ms later is throttled");
    TEST_ASSERT(!rate_limiter_allow(&rl, 50), "the counter wraps: 66 ms after the last accepted frame is still throttled");
    TEST_ASSERT(rate_limiter_allow(&rl, 0xFFFFFFF0u + 100u), "100 ms after the last accepted frame (across the wrap) is allowed");

    sensor_diagnostics_t diag;
    sensor_diagnostics_init(&diag);
    sensor_diagnostics_note_accepted_frame(&diag, 0xFFFFFFFEu);
    TEST_ASSERT(diag.last_interarrival_ms == 0, "the first accepted frame has no interval");
    sensor_diagnostics_note_accepted_frame(&diag, 8);
    TEST_ASSERT(diag.last_interarrival_ms == 10, "the interval across the counter wrap is the real elapsed time");

    sensor_diagnostics_note_bus_reset(&diag);
    sensor_diagnostics_note_bus_reset(&diag);
    TEST_ASSERT(diag.bus_reset_count == 2 && diag.frame_errors == 0, "bus resets are counted on their own");
}

static void link_end_to_end(int *failures)
{
    rate_limiter_t rl;
    sensor_freshness_t fresh;
    sensor_diagnostics_t diag;
    sensor_thermal_reading_t reading;
    rate_limiter_init(&rl, 100);
    sensor_freshness_init(&fresh);
    sensor_diagnostics_init(&diag);

    uint8_t payload[2] = { 0x27, 0x10 }; // 100.00 degrees
    uint8_t buf[SENSOR_FRAME_MAX_SIZE];
    uint8_t n = sensor_frame_encode(SENSOR_ID_THERMAL, 1, 5, payload, 2, buf);

    TEST_ASSERT(vision_sensor_link_process_frame(&rl, &fresh, &diag, NULL, 0, 0, &reading) == false && diag.disconnect_count == 1, "a missing buffer counts as a disconnect");
    TEST_ASSERT(vision_sensor_link_process_frame(&rl, &fresh, &diag, buf, n, 1000, &reading) && reading.temp_centidegrees_c == 10000, "a good frame is accepted and decoded");
    n = sensor_frame_encode(SENSOR_ID_THERMAL, 2, 6, payload, 2, buf);
    TEST_ASSERT(!vision_sensor_link_process_frame(&rl, &fresh, &diag, buf, n, 1050, &reading) && diag.rate_limited_count == 1, "the next frame 50 ms later is throttled and counted");

    uint8_t bad_value[2] = { 0x7F, 0xFF };
    n = sensor_frame_encode(SENSOR_ID_THERMAL, 2, 6, bad_value, 2, buf);
    TEST_ASSERT(!vision_sensor_link_process_frame(&rl, &fresh, &diag, buf, n, 2000, &reading) && diag.out_of_range_count == 1, "an impossible temperature is counted as out of range");
    n = sensor_frame_encode(SENSOR_ID_THERMAL, 3, 7, payload, 2, buf);
    TEST_ASSERT(vision_sensor_link_process_frame(&rl, &fresh, &diag, buf, n, 2000, &reading), "a refused reading did not use up the rate window");

    n = sensor_frame_encode(SENSOR_ID_RGB_TRIGGER, 4, 8, payload, 2, buf);
    TEST_ASSERT(!vision_sensor_link_process_frame(&rl, &fresh, &diag, buf, n, 9000, &reading) && diag.unsupported_sensor_count == 1, "a frame from another sensor is counted apart and never read as a temperature");
    n = sensor_frame_encode(0x77, 5, 9, payload, 2, buf);
    TEST_ASSERT(!vision_sensor_link_process_frame(&rl, &fresh, &diag, buf, n, 9000, &reading) && diag.unsupported_sensor_count == 2, "an unknown sensor id is counted apart too");

    buf[3] ^= 1;
    TEST_ASSERT(!vision_sensor_link_process_frame(&rl, &fresh, &diag, buf, n, 9100, &reading) && diag.frame_errors == 1, "a corrupted frame is counted as a frame error");

    TEST_ASSERT(!vision_sensor_link_process_frame(NULL, &fresh, &diag, buf, n, 9100, &reading), "without a rate limiter the link refuses");
    TEST_ASSERT(!vision_sensor_link_process_frame(&rl, NULL, &diag, buf, n, 9100, &reading), "without a freshness state the link refuses");
    TEST_ASSERT(!vision_sensor_link_process_frame(&rl, &fresh, NULL, buf, n, 9100, &reading), "without diagnostics the link refuses");
}

static void freshness_and_silence(int *failures)
{
    rate_limiter_t rl;
    sensor_freshness_t fresh;
    sensor_diagnostics_t diag;
    sensor_thermal_reading_t reading;
    rate_limiter_init(&rl, 10);
    sensor_freshness_init(&fresh);
    sensor_diagnostics_init(&diag);
    uint8_t payload[2] = { 0x07, 0xD0 }; // 20.00 degrees
    uint8_t buf[SENSOR_FRAME_MAX_SIZE];

    uint8_t n = sensor_frame_encode(SENSOR_ID_THERMAL, 5, 1000, payload, 2, buf);
    TEST_ASSERT(vision_sensor_link_process_frame(&rl, &fresh, &diag, buf, n, 1003, &reading), "the first frame is accepted");
    TEST_ASSERT(diag.last_sensor_latency_ms == 3, "the delay between the sensor timestamp and the arrival is recorded");

    // The same frame again (a sensor re-sending its last buffer) is a replay, and says so; it is not mistaken for a rate-limited frame.
    TEST_ASSERT(!vision_sensor_link_process_frame(&rl, &fresh, &diag, buf, n, 1500, &reading) && diag.replay_count == 1 && diag.rate_limited_count == 0, "a repeated frame is a replay, not a new reading");

    // An older frame that arrives late is refused too.
    n = sensor_frame_encode(SENSOR_ID_THERMAL, 4, 990, payload, 2, buf);
    TEST_ASSERT(!vision_sensor_link_process_frame(&rl, &fresh, &diag, buf, n, 1600, &reading) && diag.replay_count == 2, "a reordered older frame is refused");

    // A sequence that advances over a frozen timestamp is a stale sensor.
    n = sensor_frame_encode(SENSOR_ID_THERMAL, 6, 1000, payload, 2, buf);
    TEST_ASSERT(!vision_sensor_link_process_frame(&rl, &fresh, &diag, buf, n, 1700, &reading) && diag.stale_count == 1, "a frame whose timestamp did not advance is stale");

    // The refused frames did not move the baseline: the next genuine frame is accepted.
    n = sensor_frame_encode(SENSOR_ID_THERMAL, 6, 1100, payload, 2, buf);
    TEST_ASSERT(vision_sensor_link_process_frame(&rl, &fresh, &diag, buf, n, 1800, &reading), "a genuinely newer frame is accepted after the refused ones");
    TEST_ASSERT(diag.last_interarrival_ms == 797, "the inter-arrival time is measured between accepted frames only");

    // 8-bit sequence wrap-around and 32-bit timestamp wrap-around count as forward progress.
    sensor_freshness_t wrap;
    sensor_freshness_init(&wrap);
    sensor_freshness_commit(&wrap, 255, 0xFFFFFFF0u);
    TEST_ASSERT(sensor_freshness_check(&wrap, 0, 5) == SENSOR_FRESH, "255 -> 0 and a wrapped millisecond counter are forward progress");
    TEST_ASSERT(sensor_freshness_check(&wrap, 255, 5) == SENSOR_REPLAYED, "the same sequence is a replay");
    TEST_ASSERT(sensor_freshness_check(&wrap, 127, 5) == SENSOR_REPLAYED, "a step of 128 reads as going backwards");
    TEST_ASSERT(sensor_freshness_check(&wrap, 126, 5) == SENSOR_FRESH, "a step of 127 is the furthest forward jump");
    TEST_ASSERT(sensor_freshness_check(&wrap, 0, 0xFFFFFFF0u) == SENSOR_STALE, "an unchanged timestamp is stale");

    // A payload of the wrong size is a malformed frame, not an impossible temperature.
    uint8_t three[3] = { 1, 2, 3 };
    n = sensor_frame_encode(SENSOR_ID_THERMAL, 7, 1200, three, 3, buf);
    TEST_ASSERT(!vision_sensor_link_process_frame(&rl, &fresh, &diag, buf, n, 1900, &reading) && diag.malformed_payload_count == 1 && diag.out_of_range_count == 0, "a payload of the wrong length is counted as malformed");

    // Silence: reported once, forgets the freshness baseline, and a frame ends it.
    TEST_ASSERT(!vision_sensor_link_tick(&fresh, &diag, 2000, 1000), "200 ms after the last accepted frame there is no silence yet");
    TEST_ASSERT(vision_sensor_link_tick(&fresh, &diag, 2800, 1000), "1000 ms without an accepted frame is a silence");
    TEST_ASSERT(!vision_sensor_link_tick(&fresh, &diag, 3000, 1000) && diag.disconnect_count == 1, "the same silence is not counted twice");
    TEST_ASSERT(!fresh.has_last, "after a silence the freshness baseline is forgotten (the sensor may have restarted its counters)");
    n = sensor_frame_encode(SENSOR_ID_THERMAL, 1, 5, payload, 2, buf);
    TEST_ASSERT(vision_sensor_link_process_frame(&rl, &fresh, &diag, buf, n, 3100, &reading), "a sensor that restarted its counters is accepted again");
    TEST_ASSERT(!diag.silent, "an accepted frame ends the silence");
    TEST_ASSERT(vision_sensor_link_tick(&fresh, &diag, 4200, 1000) && diag.disconnect_count == 2, "a later silence is a new event");

    sensor_diagnostics_t fresh_diag;
    sensor_diagnostics_init(&fresh_diag);
    TEST_ASSERT(!sensor_diagnostics_check_silence(&fresh_diag, 99999, 1), "a link that never delivered a frame has no silence to report");
}

void run_robustness_tests(int *failures)
{
    null_guards(failures);
    truncation_and_corruption(failures);
    round_trips(failures);
    reading_range_edges(failures);
    clock_wraparound(failures);
    link_end_to_end(failures);
    freshness_and_silence(failures);
}
