// =============================================================================
// URTC-VISION-TOOL Firmware - Sensor reading validation: sensor_reading.c
// Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
// GPL-3.0 - see LICENSE
// =============================================================================
#include "sensor_reading.h"
#include <stddef.h>

sensor_reading_status_t sensor_reading_validate_thermal(const uint8_t *payload, uint8_t len, sensor_thermal_reading_t *out_reading)
{
    if (payload == NULL || out_reading == NULL) {
        return SENSOR_READING_ERR_WRONG_PAYLOAD_LEN;
    }
    if (len != 2u) {
        return SENSOR_READING_ERR_WRONG_PAYLOAD_LEN;
    }

    int16_t temp = (int16_t)(uint16_t)(payload[0] | ((uint16_t)payload[1] << 8));
    if (temp < SENSOR_READING_MIN_TEMP_CENTIDEGREES_C || temp > SENSOR_READING_MAX_TEMP_CENTIDEGREES_C) {
        return SENSOR_READING_ERR_TEMP_OUT_OF_RANGE;
    }

    out_reading->temp_centidegrees_c = temp;
    return SENSOR_READING_OK;
}
