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
    sensor_freshness_t *fresh,
    sensor_diagnostics_t *diag,
    const uint8_t *buf,
    uint8_t buf_len,
    uint32_t now_ms,
    sensor_thermal_reading_t *out_reading)
{
    if (rl == NULL || fresh == NULL || diag == NULL) {
        return false; // fail closed: without its state the link cannot judge a frame
    }
    if (buf == NULL) {
        sensor_diagnostics_note_disconnect(diag);
        return false;
    }

    sensor_frame_t frame;
    if (sensor_frame_parse(buf, buf_len, &frame) != SENSOR_FRAME_OK) {
        sensor_diagnostics_note_frame_error(diag);
        return false; // a bad/truncated/corrupted frame never reaches reading validation
    }

    // Only the thermal camera is read on this link. A frame of any other sensor (the RGB trigger, or an id nobody knows) used to be taken for a temperature as soon as its
    // payload had two bytes; it is counted apart and never reaches the reading validation.
    if (frame.sensor_id != SENSOR_ID_THERMAL) {
        sensor_diagnostics_note_unsupported_sensor(diag);
        return false;
    }

    // The content is checked BEFORE the rate limiter is spent: a bad frame (out of range, wrong length) must not use up the window and make the next, good frame look too fast.
    sensor_thermal_reading_t reading;
    switch (sensor_reading_validate_thermal(frame.payload, frame.len, &reading)) {
        case SENSOR_READING_OK:
            break;
        case SENSOR_READING_ERR_WRONG_PAYLOAD_LEN:
            sensor_diagnostics_note_malformed_payload(diag);
            return false; // a payload of the wrong size is a malformed frame, not an impossible temperature
        case SENSOR_READING_ERR_TEMP_OUT_OF_RANGE:
        default:
            sensor_diagnostics_note_out_of_range(diag);
            return false; // a well-formed frame carrying an impossible reading is refused
    }

    // A repeated, older or frozen frame is refused before it can spend the rate window; the baseline only moves for a frame that is accepted below.
    switch (sensor_freshness_check(fresh, frame.seq, frame.timestamp_ms)) {
        case SENSOR_FRESH:
            break;
        case SENSOR_STALE:
            sensor_diagnostics_note_stale(diag);
            return false;
        case SENSOR_REPLAYED:
        default:
            sensor_diagnostics_note_replay(diag);
            return false;
    }

    if (!rate_limiter_allow(rl, now_ms)) {
        sensor_diagnostics_note_rate_limited(diag);
        return false; // a real frame arriving too fast is throttled, not trusted
    }

    sensor_freshness_commit(fresh, frame.seq, frame.timestamp_ms);
    sensor_diagnostics_note_accepted_frame(diag, now_ms);
    sensor_diagnostics_note_sensor_latency(diag, now_ms, frame.timestamp_ms);
    if (out_reading != NULL) {
        *out_reading = reading;
    }
    return true;
}

bool vision_sensor_link_tick(
    sensor_freshness_t *fresh,
    sensor_diagnostics_t *diag,
    uint32_t now_ms,
    uint32_t silence_timeout_ms)
{
    if (!sensor_diagnostics_check_silence(diag, now_ms, silence_timeout_ms)) {
        return false;
    }
    sensor_freshness_reset(fresh);
    return true;
}
