// =============================================================================
// URTC-COMMON - firmware_base/urtc_frame.h
// Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
// GPL-3.0-or-later - see LICENSE
// =============================================================================
// The frame layer of the serial links of the tool rack and of the vision sensor, written once. Both links
// frame their messages the same way and differ only in where the length byte sits:
//
//   [SOF][VERSION] ... header fields ... [LEN] [PAYLOAD (0..max)] [CRC-8 of everything before it]
//
//   rack:   SOF 0xA5, version 2, LEN at index 4 (SEQ and CMD before it)
//   sensor: SOF 0xB6, version 2, LEN at index 8 (SENSOR_ID, SEQ and a 4-byte timestamp before it)
//
// A format is a `urtc_frame_format_t`; `urtc_frame_validate` decides whether a buffer holds one good frame of it, in
// this order, and a buffer that fails a check is never partly trusted: incomplete (too short for the smallest
// frame, or for the length it announces), wrong start byte, unsupported version, length above the maximum, bad
// CRC. `urtc_frame_start` and `urtc_frame_seal` write the other direction. The meaning of the header fields and of
// the payload stays in each repository.
//
// The statuses have the same order as the status enumerations of both repositories (0 ok, 1 incomplete, 2 bad
// start byte, 3 unsupported version, 4 length out of range, 5 CRC mismatch), which the shared vectors rely on.
//
// Copied with `python tools/vendor_copy.py sync TARGET --set firmware_frame`; needs urtc_crc8.h next to it. Header
// only, so no build list has to change.
#ifndef URTC_FRAME_H
#define URTC_FRAME_H

#include <stddef.h>
#include <stdint.h>

#include "urtc_crc8.h"

typedef struct {
    uint8_t sof;           // start byte
    uint8_t version;       // the only protocol version this link accepts
    uint8_t length_index;  // position of the payload length byte (the header ends there)
    uint8_t max_payload;   // longest payload the format allows
} urtc_frame_format_t;

typedef enum {
    URTC_FRAME_OK = 0,
    URTC_FRAME_INCOMPLETE,            // fewer bytes than the frame needs: keep buffering, it is not corrupt
    URTC_FRAME_BAD_SOF,
    URTC_FRAME_UNSUPPORTED_VERSION,
    URTC_FRAME_LENGTH_OUT_OF_RANGE,
    URTC_FRAME_CRC_MISMATCH,
} urtc_frame_status_t;

// Bytes before the payload (the length byte included).
static inline uint8_t urtc_frame_header_size(const urtc_frame_format_t *format)
{
    return (uint8_t)(format->length_index + 1u);
}

// Total size of a frame with `payload_len` payload bytes: header, payload and the CRC.
static inline uint8_t urtc_frame_total_size(const urtc_frame_format_t *format, uint8_t payload_len)
{
    return (uint8_t)(urtc_frame_header_size(format) + payload_len + 1u);
}

// Decides whether `buf` (`buf_len` bytes) starts with one good frame. On URTC_FRAME_OK `*total_len` is the size of
// that frame; bytes after it are not looked at. Anything else leaves `*total_len` alone.
static inline urtc_frame_status_t urtc_frame_validate(const urtc_frame_format_t *format, const uint8_t *buf, uint8_t buf_len, uint8_t *total_len)
{
    if (format == NULL || buf == NULL || total_len == NULL) {
        return URTC_FRAME_INCOMPLETE;
    }
    // The smallest frame has no payload: the header and the CRC.
    if (buf_len < urtc_frame_total_size(format, 0u)) {
        return URTC_FRAME_INCOMPLETE;
    }
    if (buf[0] != format->sof) {
        return URTC_FRAME_BAD_SOF;
    }
    if (buf[1] != format->version) {
        return URTC_FRAME_UNSUPPORTED_VERSION;
    }
    const uint8_t payload_len = buf[format->length_index];
    if (payload_len > format->max_payload) {
        return URTC_FRAME_LENGTH_OUT_OF_RANGE;
    }
    const uint8_t covered = (uint8_t)(urtc_frame_header_size(format) + payload_len);
    if (buf_len < (uint8_t)(covered + 1u)) {
        return URTC_FRAME_INCOMPLETE;
    }
    if (urtc_crc8(buf, covered) != buf[covered]) {
        return URTC_FRAME_CRC_MISMATCH;
    }
    *total_len = (uint8_t)(covered + 1u);
    return URTC_FRAME_OK;
}

// Writes the start byte, the version and the length byte of a frame about to be built. The caller fills the other
// header fields and the payload, then calls urtc_frame_seal.
static inline void urtc_frame_start(const urtc_frame_format_t *format, uint8_t *buf, uint8_t payload_len)
{
    buf[0] = format->sof;
    buf[1] = format->version;
    buf[format->length_index] = payload_len;
}

// Writes the CRC after the header and the payload already in `buf`; returns the size of the whole frame.
static inline uint8_t urtc_frame_seal(const urtc_frame_format_t *format, uint8_t *buf, uint8_t payload_len)
{
    const uint8_t covered = (uint8_t)(urtc_frame_header_size(format) + payload_len);
    buf[covered] = urtc_crc8(buf, covered);
    return (uint8_t)(covered + 1u);
}

#endif // URTC_FRAME_H
