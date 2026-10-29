// =============================================================================
// URTC-VISION-TOOL Firmware - tests for sensor_rx.c
// Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
// GPL-3.0-or-later - see LICENSE
// =============================================================================
// The interrupt-safe receive path: the bytes of the scenarios go in one at a time through the call an interrupt would make
// (sensor_rx_on_byte) and come out through the call of the main loop (sensor_rx_poll).
#include "test_runner.h"
#include "../src/sensor_frame.h"
#include "../src/sensor_rx.h"

typedef struct {
    sensor_rx_t rx;
    rate_limiter_t rl;
    sensor_freshness_t fresh;
    sensor_diagnostics_t diag;
} rig_t;

static void rig_init(rig_t *r)
{
    sensor_rx_init(&r->rx);
    rate_limiter_init(&r->rl, 50);
    sensor_freshness_init(&r->fresh);
    sensor_diagnostics_init(&r->diag);
}

static uint8_t thermal_frame(uint8_t *buf, uint8_t seq, uint32_t ts, int16_t centi)
{
    const uint8_t payload[2] = {(uint8_t)((uint16_t)centi >> 8), (uint8_t)((uint16_t)centi & 0xFFu)};
    return sensor_frame_encode(SENSOR_ID_THERMAL, seq, ts, payload, 2, buf);
}

static void feed(rig_t *r, const uint8_t *bytes, uint8_t len)
{
    for (uint8_t i = 0; i < len; i++) {
        (void)sensor_rx_on_byte(&r->rx, bytes[i]);
    }
}

void run_sensor_rx_tests(int *failures)
{
    uint8_t frame[SENSOR_FRAME_MAX_SIZE];
    sensor_thermal_reading_t reading = {0};
    rig_t r;

    // Argument checks fail closed.
    rig_init(&r);
    TEST_ASSERT(!sensor_rx_on_byte(NULL, 1), "a NULL receiver takes no byte");
    sensor_rx_init(NULL);
    TEST_ASSERT(!sensor_rx_poll(NULL, &r.rl, &r.fresh, &r.diag, 0, &reading), "poll refuses a NULL receiver");
    TEST_ASSERT(!sensor_rx_poll(&r.rx, NULL, &r.fresh, &r.diag, 0, &reading), "poll refuses a NULL rate limiter");
    TEST_ASSERT(!sensor_rx_poll(&r.rx, &r.rl, NULL, &r.diag, 0, &reading), "poll refuses a NULL freshness");
    TEST_ASSERT(!sensor_rx_poll(&r.rx, &r.rl, &r.fresh, NULL, 0, &reading), "poll refuses a NULL diagnostics");
    TEST_ASSERT(!sensor_rx_poll(&r.rx, &r.rl, &r.fresh, &r.diag, 0, NULL), "poll refuses a NULL output");
    TEST_ASSERT(!sensor_rx_poll(&r.rx, &r.rl, &r.fresh, &r.diag, 0, &reading), "an empty ring yields nothing");

    // A frame that arrives one byte at a time gives one reading, and only when its last byte is in.
    rig_init(&r);
    uint8_t len = thermal_frame(frame, 1, 1000, 2000);
    feed(&r, frame, (uint8_t)(len - 1));
    TEST_ASSERT(!sensor_rx_poll(&r.rx, &r.rl, &r.fresh, &r.diag, 1000, &reading), "a frame one byte short yields nothing yet");
    TEST_ASSERT(r.diag.frame_errors == 0, "and is not counted as an error: it is only incomplete");
    feed(&r, &frame[len - 1], 1);
    TEST_ASSERT(sensor_rx_poll(&r.rx, &r.rl, &r.fresh, &r.diag, 1001, &reading), "the last byte completes the frame");
    TEST_ASSERT(reading.temp_centidegrees_c == 2000, "the reading is the one that was sent");
    TEST_ASSERT(!sensor_rx_poll(&r.rx, &r.rl, &r.fresh, &r.diag, 1002, &reading), "nothing is left");

    // Noise between frames is skipped without a count.
    rig_init(&r);
    const uint8_t noise[4] = {0x00, 0x13, 0xFF, 0x42};
    feed(&r, noise, 4);
    len = thermal_frame(frame, 1, 1000, 2100);
    feed(&r, frame, len);
    TEST_ASSERT(sensor_rx_poll(&r.rx, &r.rl, &r.fresh, &r.diag, 1000, &reading) && reading.temp_centidegrees_c == 2100, "a frame after noise is found");
    TEST_ASSERT(r.diag.frame_errors == 0, "noise outside a frame is not an error");

    // A damaged frame is counted, and the good frame right behind it is still read (resynchronisation).
    rig_init(&r);
    len = thermal_frame(frame, 1, 1000, 2000);
    frame[len - 1] ^= 0x55u;                                  // wrong CRC
    feed(&r, frame, len);
    uint8_t good[SENSOR_FRAME_MAX_SIZE];
    const uint8_t good_len = thermal_frame(good, 2, 1100, 2200);
    feed(&r, good, good_len);
    TEST_ASSERT(sensor_rx_poll(&r.rx, &r.rl, &r.fresh, &r.diag, 1100, &reading) && reading.temp_centidegrees_c == 2200, "the good frame after a damaged one is read");
    TEST_ASSERT(r.diag.frame_errors >= 1, "the damaged frame was counted");

    // A start byte inside the damaged candidate is a possible start of the next frame.
    rig_init(&r);
    const uint8_t lone_sof[3] = {SENSOR_FRAME_SOF, 0x99, 0x98};   // a start byte and a wrong version
    feed(&r, lone_sof, 3);
    len = thermal_frame(frame, 1, 1000, 1900);
    feed(&r, frame, len);
    TEST_ASSERT(sensor_rx_poll(&r.rx, &r.rl, &r.fresh, &r.diag, 1000, &reading) && reading.temp_centidegrees_c == 1900, "a frame is found right behind a false start byte");

    // A half frame that waited too long is dropped; the next frame is read.
    rig_init(&r);
    len = thermal_frame(frame, 1, 1000, 2000);
    feed(&r, frame, 6);
    TEST_ASSERT(!sensor_rx_poll(&r.rx, &r.rl, &r.fresh, &r.diag, 1000, &reading), "six bytes are not a frame");
    len = thermal_frame(good, 2, 1200, 2300);
    feed(&r, good, len);
    TEST_ASSERT(sensor_rx_poll(&r.rx, &r.rl, &r.fresh, &r.diag, 1000 + SENSOR_RX_BYTE_TIMEOUT_MS + 1, &reading) && reading.temp_centidegrees_c == 2300, "after the timeout the half frame is dropped and the next frame is read");
    TEST_ASSERT(r.rx.timeouts == 1 && r.diag.frame_errors == 1, "the dropped half frame is counted once");

    // The ring overflowing loses bytes, counts them, and never yields a wrong reading.
    rig_init(&r);
    uint8_t dropped_total = 0;
    for (uint8_t i = 0; i < 80; i++) {
        if (!sensor_rx_on_byte(&r.rx, 0xAA)) {
            dropped_total++;
        }
    }
    TEST_ASSERT(dropped_total == 80u - (SENSOR_RX_RING_SIZE - 1u), "a full ring drops what does not fit");
    TEST_ASSERT(!sensor_rx_poll(&r.rx, &r.rl, &r.fresh, &r.diag, 1000, &reading), "bytes that are not a frame yield nothing");
    TEST_ASSERT(r.rx.overflow_bytes == dropped_total, "the overflow is counted");

    // Several frames queued: one reading per poll, in order, none lost.
    rig_init(&r);
    for (uint8_t i = 0; i < 3; i++) {
        len = thermal_frame(frame, (uint8_t)(i + 1), 1000u + 100u * i, (int16_t)(2000 + 10 * i));
        feed(&r, frame, len);
    }
    for (uint8_t i = 0; i < 3; i++) {
        TEST_ASSERT(sensor_rx_poll(&r.rx, &r.rl, &r.fresh, &r.diag, 1000u + 100u * i, &reading) && reading.temp_centidegrees_c == 2000 + 10 * i, "queued frames come out one per poll, in order");
    }
    TEST_ASSERT(!sensor_rx_poll(&r.rx, &r.rl, &r.fresh, &r.diag, 1400, &reading), "and then nothing");
}
