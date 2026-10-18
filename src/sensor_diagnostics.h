// =============================================================================
// URTC-VISION-TOOL Firmware - Sensor field diagnostics: sensor_diagnostics.h
// Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
// GPL-3.0 - see LICENSE
// =============================================================================
// Real, dedicated field-support counters - the review's own
// "separar diagnostico de salida de control y mantener contadores de
// error, latencia y reinicio de bus". This module never makes an
// accept/reject decision itself - sensor_frame.c/sensor_reading.c/
// rate_limiter.c/sensor_freshness.c do that; this only records what they
// decided, so a diagnostics bug can never accidentally influence which frames
// get accepted.
//
// Execution context: the counters are plain memory. Update them and read them
// from ONE context (the main loop). A receive interrupt should only copy the
// raw bytes into a ring buffer; reading several counters from the main loop
// while an interrupt updates them would give an inconsistent snapshot.
#ifndef SENSOR_DIAGNOSTICS_H
#define SENSOR_DIAGNOSTICS_H

#include <stdbool.h>
#include <stdint.h>

typedef struct {
    uint32_t frame_errors;       // sensor_frame_parse() rejections (bad SOF/version/length/CRC/incomplete)
    uint32_t out_of_range_count; // a thermal payload of the right size whose temperature is impossible
    uint32_t malformed_payload_count; // a thermal payload of the wrong size
    uint32_t rate_limited_count; // rate_limiter_allow() rejections
    uint32_t unsupported_sensor_count; // well-formed frames from a sensor id this link does not read (an unknown id, or the RGB trigger)
    uint32_t replay_count;       // frames whose sequence number is not newer than the last accepted one
    uint32_t stale_count;        // frames whose sensor timestamp did not advance (a sensor re-sending frozen data)
    uint32_t disconnect_count;   // explicit "sensor went silent" events (a missing buffer, or a silence that outlasted the timeout)
    uint32_t bus_reset_count;    // incremented by the bus driver when it resets the bus (see sensor_diagnostics_note_bus_reset)
    uint32_t last_interarrival_ms;    // time between the two most recent accepted frames, as the MCU saw them arrive
    uint32_t last_sensor_latency_ms;  // MCU receive time minus the sensor timestamp of the last accepted frame (meaningful only when both clocks share one epoch)
    bool has_last_accept_ms;
    uint32_t last_accept_ms;
    bool silent;                 // a silence has been reported and no frame has been accepted since
} sensor_diagnostics_t;

void sensor_diagnostics_init(sensor_diagnostics_t *diag);
void sensor_diagnostics_note_frame_error(sensor_diagnostics_t *diag);
void sensor_diagnostics_note_out_of_range(sensor_diagnostics_t *diag);
void sensor_diagnostics_note_malformed_payload(sensor_diagnostics_t *diag);
void sensor_diagnostics_note_rate_limited(sensor_diagnostics_t *diag);
void sensor_diagnostics_note_unsupported_sensor(sensor_diagnostics_t *diag);
void sensor_diagnostics_note_replay(sensor_diagnostics_t *diag);
void sensor_diagnostics_note_stale(sensor_diagnostics_t *diag);
void sensor_diagnostics_note_disconnect(sensor_diagnostics_t *diag);

// The receive path never resets the bus itself: whoever drives the bus (the
// I2C/SPI driver, once it exists) calls this each time it does.
void sensor_diagnostics_note_bus_reset(sensor_diagnostics_t *diag);

// Records a real accepted frame at `now_ms`, updating `last_interarrival_ms`
// against the previous accepted frame's own time (0 on the very first
// accepted frame - there's nothing real to measure against yet). It also ends
// a reported silence.
void sensor_diagnostics_note_accepted_frame(sensor_diagnostics_t *diag, uint32_t now_ms);

// Records the sensor-to-MCU delay of an accepted frame: `now_ms` minus the
// timestamp the sensor put in the frame. Only meaningful when the sensor clock
// and the MCU clock count from the same instant (a synchronisation this module
// cannot provide).
void sensor_diagnostics_note_sensor_latency(sensor_diagnostics_t *diag, uint32_t now_ms, uint32_t sensor_timestamp_ms);

// Silence detection for the main loop: after a frame was accepted, reports
// (and counts, once per silence) a link that has delivered nothing for
// `timeout_ms`. Returns true exactly when it reports a new silence.
bool sensor_diagnostics_check_silence(sensor_diagnostics_t *diag, uint32_t now_ms, uint32_t timeout_ms);

#endif // SENSOR_DIAGNOSTICS_H
