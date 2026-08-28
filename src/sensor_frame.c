// =============================================================================
// URTC-VISION-TOOL Firmware - Sensor frame protocol: sensor_frame.c
// Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
// GPL-3.0 - see LICENSE
// =============================================================================
#include "sensor_frame.h"
#include <stddef.h>

uint8_t sensor_frame_crc8(const uint8_t *data, uint8_t len)
{
    uint8_t crc = 0x00u;
    for (uint8_t i = 0; i < len; i++) {
        crc ^= data[i];
        for (uint8_t bit = 0; bit < 8u; bit++) {
            if (crc & 0x80u) {
                crc = (uint8_t)((crc << 1) ^ 0x07u);
            } else {
                crc = (uint8_t)(crc << 1);
            }
        }
    }
    return crc;
}

sensor_frame_status_t sensor_frame_parse(const uint8_t *buf, uint8_t buf_len, sensor_frame_t *out_frame)
{
    if (buf == NULL || out_frame == NULL) {
        return SENSOR_FRAME_ERR_INCOMPLETE;
    }
    // Smallest real frame: SOF+VERSION+SENSOR_ID+SEQ+TIMESTAMP(4)+LEN+CRC, zero payload.
    if (buf_len < 10u) {
        return SENSOR_FRAME_ERR_INCOMPLETE;
    }
    if (buf[0] != SENSOR_FRAME_SOF) {
        return SENSOR_FRAME_ERR_BAD_SOF;
    }
    uint8_t version = buf[1];
    if (version != SENSOR_FRAME_VERSION) {
        return SENSOR_FRAME_ERR_UNSUPPORTED_VERSION;
    }
    uint8_t len = buf[8];
    if (len > SENSOR_FRAME_MAX_PAYLOAD) {
        return SENSOR_FRAME_ERR_LENGTH_OUT_OF_RANGE;
    }
    uint8_t header_and_payload_len = (uint8_t)(9u + len);
    uint8_t total_len = (uint8_t)(header_and_payload_len + 1u);
    if (buf_len < total_len) {
        return SENSOR_FRAME_ERR_INCOMPLETE;
    }
    uint8_t computed_crc = sensor_frame_crc8(buf, header_and_payload_len);
    uint8_t received_crc = buf[header_and_payload_len];
    if (computed_crc != received_crc) {
        return SENSOR_FRAME_ERR_CRC_MISMATCH;
    }

    out_frame->version = version;
    out_frame->sensor_id = buf[2];
    out_frame->seq = buf[3];
    out_frame->timestamp_ms = (uint32_t)buf[4]
        | ((uint32_t)buf[5] << 8)
        | ((uint32_t)buf[6] << 16)
        | ((uint32_t)buf[7] << 24);
    out_frame->len = len;
    for (uint8_t i = 0; i < len; i++) {
        out_frame->payload[i] = buf[9u + i];
    }
    return SENSOR_FRAME_OK;
}

uint8_t sensor_frame_encode(uint8_t sensor_id, uint8_t seq, uint32_t timestamp_ms, const uint8_t *payload, uint8_t payload_len, uint8_t *out_buf)
{
    if (out_buf == NULL || payload_len > SENSOR_FRAME_MAX_PAYLOAD) {
        return 0;
    }
    if (payload_len > 0u && payload == NULL) {
        return 0;
    }
    out_buf[0] = SENSOR_FRAME_SOF;
    out_buf[1] = SENSOR_FRAME_VERSION;
    out_buf[2] = sensor_id;
    out_buf[3] = seq;
    out_buf[4] = (uint8_t)(timestamp_ms & 0xFFu);
    out_buf[5] = (uint8_t)((timestamp_ms >> 8) & 0xFFu);
    out_buf[6] = (uint8_t)((timestamp_ms >> 16) & 0xFFu);
    out_buf[7] = (uint8_t)((timestamp_ms >> 24) & 0xFFu);
    out_buf[8] = payload_len;
    for (uint8_t i = 0; i < payload_len; i++) {
        out_buf[9u + i] = payload[i];
    }
    uint8_t header_and_payload_len = (uint8_t)(9u + payload_len);
    out_buf[header_and_payload_len] = sensor_frame_crc8(out_buf, header_and_payload_len);
    return (uint8_t)(header_and_payload_len + 1u);
}
