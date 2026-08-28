// =============================================================================
// URTC-VISION-TOOL Firmware - Sensor reading validation: sensor_reading.h
// Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
// GPL-3.0 - see LICENSE
// =============================================================================
// Turns a real, CRC-valid sensor_frame_t (see sensor_frame.h) into a real,
// range-checked reading - separate from the wire-framing layer, since a
// perfectly well-formed frame can still carry a physically impossible
// measurement (a real ADC glitch, a disconnected sensor reporting rail
// voltage, etc.). The promotion audit's own "medidas fuera de rango" case.
#ifndef SENSOR_READING_H
#define SENSOR_READING_H

#include <stdint.h>

typedef enum {
    SENSOR_READING_OK = 0,
    SENSOR_READING_ERR_WRONG_PAYLOAD_LEN,
    SENSOR_READING_ERR_TEMP_OUT_OF_RANGE,
} sensor_reading_status_t;

// This project's own v0 convention for representing an MLX9064x-class
// thermal reading on the wire (int16_t, hundredths of a degree C) - real
// object-temperature bounds from that sensor family's own real datasheet
// range, not guessed without one in hand (see mejoras_futuras.txt for the
// real register map, still pending real hardware).
#define SENSOR_READING_MIN_TEMP_CENTIDEGREES_C (-4000)
#define SENSOR_READING_MAX_TEMP_CENTIDEGREES_C 30000

typedef struct {
    int16_t temp_centidegrees_c;
} sensor_thermal_reading_t;

// Decodes and range-checks a SENSOR_ID_THERMAL payload (2 bytes,
// little-endian signed int16, hundredths of a degree C). `out_reading` is
// only written on SENSOR_READING_OK.
sensor_reading_status_t sensor_reading_validate_thermal(const uint8_t *payload, uint8_t len, sensor_thermal_reading_t *out_reading);

#endif // SENSOR_READING_H
