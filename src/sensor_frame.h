// =============================================================================
// URTC-VISION-TOOL Firmware - Sensor frame protocol: sensor_frame.h
// Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
// GPL-3.0 - see LICENSE
// =============================================================================
// Real wire framing for the sensor->MCU link (MLX9064x thermal camera /
// RGB trigger, once the PCB wiring exists - see main.c's own note). This
// project's own v0 convention, not a copy of the real MLX9064x I2C
// register protocol (that needs the real datasheet in hand, see
// mejoras_futuras.txt) - the promotion audit's own "formalizar contrato
// de sensor/camara... para que el firmware no acepte entradas ambiguas".
// Pure byte-buffer logic, no I2C/SPI peripheral access - real and
// testable on the host today.
//
//   byte:   0     1        2         3      4..7           8      9..9+len-1   9+len
//         [SOF][VERSION][SENSOR_ID][SEQ] [TIMESTAMP_MS]  [LEN] [PAYLOAD...]   [CRC8]
//
// TIMESTAMP_MS is a 4-byte little-endian sensor-side millisecond
// timestamp - the real "cuando se midio" the audit calls for, distinct
// from whenever the MCU happens to parse the frame. CRC8 covers
// everything from SOF through the last payload byte.
#ifndef SENSOR_FRAME_H
#define SENSOR_FRAME_H

#include <stdint.h>

#define SENSOR_FRAME_SOF 0xB6u
#define SENSOR_FRAME_VERSION 1u
#define SENSOR_FRAME_MAX_PAYLOAD 16u
// SOF + VERSION + SENSOR_ID + SEQ + TIMESTAMP(4) + LEN + payload + CRC
#define SENSOR_FRAME_MAX_SIZE (9u + SENSOR_FRAME_MAX_PAYLOAD + 1u)

typedef enum {
    SENSOR_ID_THERMAL = 0x01,
    SENSOR_ID_RGB_TRIGGER = 0x02,
} sensor_id_t;

typedef enum {
    SENSOR_FRAME_OK = 0,
    SENSOR_FRAME_ERR_INCOMPLETE,             // fewer bytes than the frame needs - keep buffering, not corrupt
    SENSOR_FRAME_ERR_BAD_SOF,
    SENSOR_FRAME_ERR_UNSUPPORTED_VERSION,
    SENSOR_FRAME_ERR_LENGTH_OUT_OF_RANGE,
    SENSOR_FRAME_ERR_CRC_MISMATCH,
} sensor_frame_status_t;

typedef struct {
    uint8_t version;
    uint8_t sensor_id;
    uint8_t seq;
    uint32_t timestamp_ms;
    uint8_t len;
    uint8_t payload[SENSOR_FRAME_MAX_PAYLOAD];
} sensor_frame_t;

// Real CRC-8 (polynomial 0x07, the same SMBus-style variant used by
// sibling repo URTC-SMART-RACK's protocol.c, chosen for ecosystem
// consistency rather than reinvented) over `len` bytes starting at `data`.
uint8_t sensor_frame_crc8(const uint8_t *data, uint8_t len);

// Real parser: decodes exactly one already-delimited frame into
// `out_frame`. Returns SENSOR_FRAME_OK only when SOF, version, declared
// length and CRC are all real and consistent - `out_frame` is left
// untouched on any non-OK status, so a caller never acts on a partially
// trusted reading.
sensor_frame_status_t sensor_frame_parse(const uint8_t *buf, uint8_t buf_len, sensor_frame_t *out_frame);

// Real encoder: the inverse of sensor_frame_parse(), used by tests and
// the host-side sensor simulator to build real frames (or deliberately
// corrupted ones, by mutating the buffer afterward). Returns the real
// number of bytes written, or 0 if payload_len exceeds
// SENSOR_FRAME_MAX_PAYLOAD.
uint8_t sensor_frame_encode(uint8_t sensor_id, uint8_t seq, uint32_t timestamp_ms, const uint8_t *payload, uint8_t payload_len, uint8_t *out_buf);

#endif // SENSOR_FRAME_H
