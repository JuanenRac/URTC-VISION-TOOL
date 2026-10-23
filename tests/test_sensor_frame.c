// =============================================================================
// URTC-VISION-TOOL Firmware - tests for sensor_frame.c
// Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
// GPL-3.0-or-later - see LICENSE
// =============================================================================
#include "test_runner.h"
#include "../src/sensor_frame.h"
#include "vectors/urtc_fw_vectors.h"
#include <string.h>

void run_sensor_frame_tests(int *failures)
{
    // --- The shared checksum (urtc_crc8.h, copied from URTC-COMMON) gives the values URTC-COMMON computes on its own ---
    {
        int mismatches = 0;
        for (int i = 0; i < URTC_VEC_COUNT(URTC_VEC_CRC8); i++) {
            if (sensor_frame_crc8(URTC_VEC_CRC8[i].data, URTC_VEC_CRC8[i].len) != URTC_VEC_CRC8[i].crc) {
                mismatches++;
            }
        }
        TEST_ASSERT(mismatches == 0, "sensor_frame_crc8 gives every check value of URTC-COMMON");
        TEST_ASSERT(sensor_frame_crc8((const uint8_t *)"123456789", 9) == 0xF4, "the check text gives the CRC-8 check value 0xF4");
    }

    // --- Real round trip: encode then parse gives back the exact same frame ---
    {
        uint8_t payload[2] = {0xD0, 0x07}; // 0x07D0 = 2000 centidegrees = 20.00C
        uint8_t buf[SENSOR_FRAME_MAX_SIZE];
        uint8_t written = sensor_frame_encode(SENSOR_ID_THERMAL, 3, 123456u, payload, 2, buf);
        TEST_ASSERT(written == 9 + 2 + 1, "encode writes header + payload + CRC bytes");
        TEST_ASSERT(buf[0] == SENSOR_FRAME_SOF, "encoded frame starts with the real SOF byte");

        sensor_frame_t frame;
        sensor_frame_status_t status = sensor_frame_parse(buf, written, &frame);
        TEST_ASSERT(status == SENSOR_FRAME_OK, "a real, valid encoded frame parses as SENSOR_FRAME_OK");
        TEST_ASSERT(frame.sensor_id == SENSOR_ID_THERMAL, "parsed sensor_id matches");
        TEST_ASSERT(frame.seq == 3, "parsed seq matches");
        TEST_ASSERT(frame.timestamp_ms == 123456u, "parsed timestamp_ms matches (real 32-bit little-endian decode)");
        TEST_ASSERT(frame.len == 2, "parsed len matches");
        TEST_ASSERT(memcmp(frame.payload, payload, 2) == 0, "parsed payload bytes match exactly");
    }

    // --- Real zero-payload frame round trip ---
    {
        uint8_t buf[SENSOR_FRAME_MAX_SIZE];
        uint8_t written = sensor_frame_encode(SENSOR_ID_RGB_TRIGGER, 1, 0, NULL, 0, buf);
        TEST_ASSERT(written == 10, "a zero-payload frame is exactly 10 bytes");

        sensor_frame_t frame;
        TEST_ASSERT(sensor_frame_parse(buf, written, &frame) == SENSOR_FRAME_OK, "a real zero-payload frame parses as SENSOR_FRAME_OK");
        TEST_ASSERT(frame.len == 0, "parsed len is 0");
    }

    // --- Real corrupted CRC is rejected ---
    {
        uint8_t payload[2] = {0x00, 0x00};
        uint8_t buf[SENSOR_FRAME_MAX_SIZE];
        uint8_t written = sensor_frame_encode(SENSOR_ID_THERMAL, 1, 0, payload, 2, buf);
        buf[written - 1] ^= 0xFFu; // flip every bit of the real CRC byte

        sensor_frame_t frame;
        TEST_ASSERT(sensor_frame_parse(buf, written, &frame) == SENSOR_FRAME_ERR_CRC_MISMATCH, "a frame with a corrupted CRC byte is rejected as SENSOR_FRAME_ERR_CRC_MISMATCH");
    }

    // --- Real corrupted payload (CRC now stale) is rejected too ---
    {
        uint8_t payload[2] = {0x00, 0x00};
        uint8_t buf[SENSOR_FRAME_MAX_SIZE];
        uint8_t written = sensor_frame_encode(SENSOR_ID_THERMAL, 1, 0, payload, 2, buf);
        buf[9] ^= 0x01u; // flip a bit in the payload itself, CRC left stale

        sensor_frame_t frame;
        TEST_ASSERT(sensor_frame_parse(buf, written, &frame) == SENSOR_FRAME_ERR_CRC_MISMATCH, "a frame with corrupted payload (stale CRC) is rejected as SENSOR_FRAME_ERR_CRC_MISMATCH");
    }

    // --- Real bad SOF ---
    {
        uint8_t buf[10] = {0x00, SENSOR_FRAME_VERSION, 0, 0, 0, 0, 0, 0, 0, 0};
        sensor_frame_t frame;
        TEST_ASSERT(sensor_frame_parse(buf, 10, &frame) == SENSOR_FRAME_ERR_BAD_SOF, "a frame with the wrong SOF byte is rejected as SENSOR_FRAME_ERR_BAD_SOF");
    }

    // --- Real unsupported version ---
    {
        uint8_t payload[1] = {0};
        uint8_t buf[SENSOR_FRAME_MAX_SIZE];
        uint8_t written = sensor_frame_encode(SENSOR_ID_THERMAL, 1, 0, payload, 1, buf);
        buf[1] = (uint8_t)(SENSOR_FRAME_VERSION + 1);
        buf[written - 1] = sensor_frame_crc8(buf, written - 1); // re-sign after mutating the version byte, to isolate this check from the CRC check

        sensor_frame_t frame;
        TEST_ASSERT(sensor_frame_parse(buf, written, &frame) == SENSOR_FRAME_ERR_UNSUPPORTED_VERSION, "a real frame with a future protocol version is rejected as SENSOR_FRAME_ERR_UNSUPPORTED_VERSION");
    }

    // --- Real length declared beyond SENSOR_FRAME_MAX_PAYLOAD ---
    {
        uint8_t buf[11] = {SENSOR_FRAME_SOF, SENSOR_FRAME_VERSION, 0, 0, 0, 0, 0, 0, SENSOR_FRAME_MAX_PAYLOAD + 1, 0, 0};
        sensor_frame_t frame;
        TEST_ASSERT(sensor_frame_parse(buf, 11, &frame) == SENSOR_FRAME_ERR_LENGTH_OUT_OF_RANGE, "a declared length beyond SENSOR_FRAME_MAX_PAYLOAD is rejected as SENSOR_FRAME_ERR_LENGTH_OUT_OF_RANGE");
    }

    // --- Real incomplete/truncated buffer ---
    {
        uint8_t payload[2] = {1, 2};
        uint8_t buf[SENSOR_FRAME_MAX_SIZE];
        uint8_t written = sensor_frame_encode(SENSOR_ID_THERMAL, 1, 0, payload, 2, buf);
        sensor_frame_t frame;
        TEST_ASSERT(sensor_frame_parse(buf, (uint8_t)(written - 1), &frame) == SENSOR_FRAME_ERR_INCOMPLETE, "a real truncated frame (one byte short) is SENSOR_FRAME_ERR_INCOMPLETE, not treated as corrupt");
        TEST_ASSERT(sensor_frame_parse(buf, 4, &frame) == SENSOR_FRAME_ERR_INCOMPLETE, "a buffer shorter than even the fixed header is SENSOR_FRAME_ERR_INCOMPLETE");
    }

    // --- encode refuses an over-long payload rather than truncating it ---
    {
        uint8_t oversized_payload[SENSOR_FRAME_MAX_PAYLOAD + 1];
        memset(oversized_payload, 0xAA, sizeof(oversized_payload));
        uint8_t buf[SENSOR_FRAME_MAX_SIZE + 1];
        TEST_ASSERT(sensor_frame_encode(SENSOR_ID_THERMAL, 1, 0, oversized_payload, sizeof(oversized_payload), buf) == 0, "encode refuses a payload longer than SENSOR_FRAME_MAX_PAYLOAD rather than silently truncating it");
    }

    // --- The bytes past the declared length are cleared, not left over from an earlier frame ---
    {
        sensor_frame_t frame;
        for (uint8_t i = 0; i < SENSOR_FRAME_MAX_PAYLOAD; i++) {
            frame.payload[i] = 0xAA;
        }
        uint8_t payload[2] = {0x11, 0x22};
        uint8_t buf[SENSOR_FRAME_MAX_SIZE];
        uint8_t len = sensor_frame_encode(SENSOR_ID_THERMAL, 1, 100, payload, 2, buf);
        TEST_ASSERT(sensor_frame_parse(buf, len, &frame) == SENSOR_FRAME_OK, "the frame parses");
        int tail_clear = 1;
        for (uint8_t i = 2; i < SENSOR_FRAME_MAX_PAYLOAD; i++) {
            if (frame.payload[i] != 0) tail_clear = 0;
        }
        TEST_ASSERT(frame.payload[0] == 0x11 && frame.payload[1] == 0x22 && tail_clear, "the payload keeps its bytes and the tail after them is zero");
    }
}
