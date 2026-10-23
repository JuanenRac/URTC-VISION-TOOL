// =============================================================================
// URTC-VISION-TOOL Firmware - Host-side tests: the shared vectors (test_sensor_vectors.c)
// Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
// GPL-3.0-or-later - see LICENSE
// =============================================================================
// tests/vectors/sensor_vectors.h is written by URTC-COMMON from its own independent model of the sensor link (sensor_frame.py).
// Every frame, every parse outcome and every thermal reading in it is reproduced here by the real code of the vision head, so the
// model and the firmware cannot drift apart unnoticed. All multi-byte values are big-endian, frame version 2.
#include <string.h>

#include "../src/sensor_frame.h"
#include "../src/sensor_reading.h"
#include "test_runner.h"
#include "vectors/sensor_vectors.h"

void run_sensor_vectors_tests(int *failures)
{
    TEST_ASSERT(SENSOR_FRAME_VERSION == 2u, "the sensor frame is at version 2, the big-endian layout");

    for (int i = 0; i < SENSOR_VEC_COUNT(SENSOR_VEC_FRAMES); i++) {
        const sensor_vec_frame_t *v = &SENSOR_VEC_FRAMES[i];
        uint8_t out[SENSOR_FRAME_MAX_SIZE];
        const uint8_t n = sensor_frame_encode(v->sensor_id, v->seq, v->timestamp_ms, v->payload, v->payload_len, out);
        TEST_ASSERT(n == v->frame_len && memcmp(out, v->frame, v->frame_len) == 0, v->name);
        sensor_frame_t parsed;
        TEST_ASSERT(sensor_frame_parse(v->frame, v->frame_len, &parsed) == SENSOR_FRAME_OK && parsed.sensor_id == v->sensor_id &&
                    parsed.seq == v->seq && parsed.timestamp_ms == v->timestamp_ms && parsed.len == v->payload_len &&
                    memcmp(parsed.payload, v->payload, v->payload_len) == 0,
                    "a vector frame parses back to its fields");
    }
    for (int i = 0; i < SENSOR_VEC_COUNT(SENSOR_VEC_PARSE); i++) {
        const sensor_vec_parse_t *v = &SENSOR_VEC_PARSE[i];
        sensor_frame_t parsed;
        TEST_ASSERT((int)sensor_frame_parse(v->buf, v->len, &parsed) == v->status, v->name);
    }
    for (int i = 0; i < SENSOR_VEC_COUNT(SENSOR_VEC_THERMAL); i++) {
        const sensor_vec_thermal_t *v = &SENSOR_VEC_THERMAL[i];
        sensor_thermal_reading_t reading;
        const sensor_reading_status_t status = sensor_reading_validate_thermal(v->payload, v->len, &reading);
        TEST_ASSERT((int)status == v->status, v->name);
        if (status == SENSOR_READING_OK) {
            TEST_ASSERT((int)reading.temp_centidegrees_c == v->centidegrees, v->name);
        }
    }
}
