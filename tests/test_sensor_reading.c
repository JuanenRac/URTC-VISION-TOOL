// =============================================================================
// URTC-VISION-TOOL Firmware - tests for sensor_reading.c
// Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
// GPL-3.0 - see LICENSE
// =============================================================================
#include "test_runner.h"
#include "../src/sensor_reading.h"

void run_sensor_reading_tests(int *failures)
{
    // --- Real valid reading ---
    {
        uint8_t payload[2] = {0xD0, 0x07}; // 0x07D0 = 2000 -> 20.00C
        sensor_thermal_reading_t out;
        sensor_reading_status_t status = sensor_reading_validate_thermal(payload, 2, &out);
        TEST_ASSERT(status == SENSOR_READING_OK, "a real, in-range thermal reading validates as SENSOR_READING_OK");
        TEST_ASSERT(out.temp_centidegrees_c == 2000, "decoded temp_centidegrees_c matches (little-endian decode)");
    }

    // --- Real boundary: exactly the min/max are still valid ---
    {
        sensor_thermal_reading_t out;
        uint8_t min_payload[2] = {
            (uint8_t)(SENSOR_READING_MIN_TEMP_CENTIDEGREES_C & 0xFF),
            (uint8_t)((SENSOR_READING_MIN_TEMP_CENTIDEGREES_C >> 8) & 0xFF),
        };
        TEST_ASSERT(sensor_reading_validate_thermal(min_payload, 2, &out) == SENSOR_READING_OK, "the minimum real bound is still accepted");
        TEST_ASSERT(out.temp_centidegrees_c == SENSOR_READING_MIN_TEMP_CENTIDEGREES_C, "the decoded minimum matches exactly");

        uint8_t max_payload[2] = {
            (uint8_t)(SENSOR_READING_MAX_TEMP_CENTIDEGREES_C & 0xFF),
            (uint8_t)((SENSOR_READING_MAX_TEMP_CENTIDEGREES_C >> 8) & 0xFF),
        };
        TEST_ASSERT(sensor_reading_validate_thermal(max_payload, 2, &out) == SENSOR_READING_OK, "the maximum real bound is still accepted");
    }

    // --- Real out-of-range readings are rejected, not clamped ---
    {
        int16_t too_hot = SENSOR_READING_MAX_TEMP_CENTIDEGREES_C + 1;
        uint8_t payload[2] = {(uint8_t)((uint16_t)too_hot & 0xFF), (uint8_t)(((uint16_t)too_hot >> 8) & 0xFF)};
        sensor_thermal_reading_t out;
        TEST_ASSERT(sensor_reading_validate_thermal(payload, 2, &out) == SENSOR_READING_ERR_TEMP_OUT_OF_RANGE, "a reading one centidegree above the real max is rejected as SENSOR_READING_ERR_TEMP_OUT_OF_RANGE");
    }
    {
        int16_t too_cold = SENSOR_READING_MIN_TEMP_CENTIDEGREES_C - 1;
        uint8_t payload[2] = {(uint8_t)((uint16_t)too_cold & 0xFF), (uint8_t)(((uint16_t)too_cold >> 8) & 0xFF)};
        sensor_thermal_reading_t out;
        TEST_ASSERT(sensor_reading_validate_thermal(payload, 2, &out) == SENSOR_READING_ERR_TEMP_OUT_OF_RANGE, "a reading one centidegree below the real min is rejected as SENSOR_READING_ERR_TEMP_OUT_OF_RANGE");
    }

    // --- Real wrong payload length ---
    {
        uint8_t short_payload[1] = {0};
        sensor_thermal_reading_t out;
        TEST_ASSERT(sensor_reading_validate_thermal(short_payload, 1, &out) == SENSOR_READING_ERR_WRONG_PAYLOAD_LEN, "a 1-byte payload (thermal needs 2) is rejected as SENSOR_READING_ERR_WRONG_PAYLOAD_LEN");

        uint8_t long_payload[3] = {0, 0, 0};
        TEST_ASSERT(sensor_reading_validate_thermal(long_payload, 3, &out) == SENSOR_READING_ERR_WRONG_PAYLOAD_LEN, "a 3-byte payload is also rejected as SENSOR_READING_ERR_WRONG_PAYLOAD_LEN");
    }
}
