// =============================================================================
// URTC-VISION-TOOL Firmware - Real receive-path decision: vision_sensor_link.c
// Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
// GPL-3.0 - see LICENSE
// =============================================================================
#include "vision_sensor_link.h"

#include <stddef.h> // NULL for the disconnected receive-path check.

#include "sensor_frame.h"

bool vision_sensor_link_process_frame(
    rate_limiter_t *rl,
    sensor_diagnostics_t *diag,
    const uint8_t *buf,
    uint8_t buf_len,
    uint32_t now_ms,
    sensor_thermal_reading_t *out_reading)
{
    if (buf == NULL) {
        sensor_diagnostics_note_disconnect(diag);
        return false;
    }

    sensor_frame_t frame;
    if (sensor_frame_parse(buf, buf_len, &frame) != SENSOR_FRAME_OK) {
        sensor_diagnostics_note_frame_error(diag);
        return false; // a bad/truncated/corrupted frame never reaches reading validation
    }

    if (!rate_limiter_allow(rl, now_ms)) {
        sensor_diagnostics_note_rate_limited(diag);
        return false; // a real frame arriving too fast is throttled, not trusted
    }

    if (sensor_reading_validate_thermal(frame.payload, frame.len, out_reading) != SENSOR_READING_OK) {
        sensor_diagnostics_note_out_of_range(diag);
        return false; // a well-formed frame carrying an impossible reading is refused
    }

    sensor_diagnostics_note_accepted_frame(diag, now_ms);
    return true;
}
