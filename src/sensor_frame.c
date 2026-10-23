// =============================================================================
// URTC-VISION-TOOL Firmware - Sensor frame protocol: sensor_frame.c
// Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
// GPL-3.0-or-later - see LICENSE
// =============================================================================
#include "sensor_frame.h"
#include "urtc_crc8.h"   // the checksum shared with the tool rack protocol (copied from URTC-COMMON)
#include "urtc_frame.h"  // the frame layer shared with the tool rack protocol (copied from URTC-COMMON)
#include <stddef.h>

// The sensor frame is the shared layer with the length byte at index 8 (sensor id, sequence and the timestamp sit before it).
static const urtc_frame_format_t SENSOR_FRAME = { SENSOR_FRAME_SOF, SENSOR_FRAME_VERSION, 8u, SENSOR_FRAME_MAX_PAYLOAD };

// The statuses of the shared layer have the same order as ours; the cast below relies on it.
_Static_assert((int)URTC_FRAME_OK == (int)SENSOR_FRAME_OK, "status order: ok");
_Static_assert((int)URTC_FRAME_INCOMPLETE == (int)SENSOR_FRAME_ERR_INCOMPLETE, "status order: incomplete");
_Static_assert((int)URTC_FRAME_BAD_SOF == (int)SENSOR_FRAME_ERR_BAD_SOF, "status order: bad start byte");
_Static_assert((int)URTC_FRAME_UNSUPPORTED_VERSION == (int)SENSOR_FRAME_ERR_UNSUPPORTED_VERSION, "status order: unsupported version");
_Static_assert((int)URTC_FRAME_LENGTH_OUT_OF_RANGE == (int)SENSOR_FRAME_ERR_LENGTH_OUT_OF_RANGE, "status order: length out of range");
_Static_assert((int)URTC_FRAME_CRC_MISMATCH == (int)SENSOR_FRAME_ERR_CRC_MISMATCH, "status order: CRC mismatch");

uint8_t sensor_frame_crc8(const uint8_t *data, uint8_t len)
{
    return urtc_crc8(data, len);
}

sensor_frame_status_t sensor_frame_parse(const uint8_t *buf, uint8_t buf_len, sensor_frame_t *out_frame)
{
    if (buf == NULL || out_frame == NULL) {
        return SENSOR_FRAME_ERR_INCOMPLETE;
    }
    // Start byte, version, length, completeness and CRC are decided by the shared frame layer, in that order.
    uint8_t total_len = 0;
    const urtc_frame_status_t status = urtc_frame_validate(&SENSOR_FRAME, buf, buf_len, &total_len);
    if (status != URTC_FRAME_OK) {
        return (sensor_frame_status_t)status;
    }
    const uint8_t version = buf[1];
    const uint8_t len = buf[8];

    out_frame->version = version;
    out_frame->sensor_id = buf[2];
    out_frame->seq = buf[3];
    out_frame->timestamp_ms = ((uint32_t)buf[4] << 24)
        | ((uint32_t)buf[5] << 16)
        | ((uint32_t)buf[6] << 8)
        | (uint32_t)buf[7];
    out_frame->len = len;
    for (uint8_t i = 0; i < len; i++) {
        out_frame->payload[i] = buf[9u + i];
    }
    // The bytes past `len` are not the sender's: clear them, so a caller that
    // reuses one frame variable never sees the tail of an earlier frame there.
    for (uint8_t i = len; i < SENSOR_FRAME_MAX_PAYLOAD; i++) {
        out_frame->payload[i] = 0;
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
    urtc_frame_start(&SENSOR_FRAME, out_buf, payload_len);
    out_buf[2] = sensor_id;
    out_buf[3] = seq;
    out_buf[4] = (uint8_t)((timestamp_ms >> 24) & 0xFFu);
    out_buf[5] = (uint8_t)((timestamp_ms >> 16) & 0xFFu);
    out_buf[6] = (uint8_t)((timestamp_ms >> 8) & 0xFFu);
    out_buf[7] = (uint8_t)(timestamp_ms & 0xFFu);
    for (uint8_t i = 0; i < payload_len; i++) {
        out_buf[9u + i] = payload[i];
    }
    return urtc_frame_seal(&SENSOR_FRAME, out_buf, payload_len);
}
