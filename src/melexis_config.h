// =============================================================================
// URTC-VISION-TOOL Firmware - Thermal sensor settings: melexis_config.h
// Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
// GPL-3.0-or-later - see LICENSE
// =============================================================================
// The two settings of an MLX9064x-class thermal sensor that a person may want
// to change, with the limits that keep them safe:
//
//   refresh_hz    how often the sensor makes a frame: 0.5, 1, 2, 4, 8, 16, 32 or
//                 64 Hz (the rates the family supports). Default 2 Hz.
//   filter_level  how many frames are averaged before a reading is used:
//                 0 = off (1 frame), 1 = 2 frames, 2 = 4 frames, 3 = 8 frames.
//                 Default 0 (off).
//
// A value that is not one of those is never used and never clamped to a
// neighbour: the field keeps the value it had (the default for a fresh
// configuration) and the rejection is counted, so a typo cannot silently change
// the refresh rate. The text form is one "key=value" per line; blank lines and
// lines that start with '#' are ignored. Pure logic against caller-supplied
// text: no file, no clock, no hardware.
#ifndef MELEXIS_CONFIG_H
#define MELEXIS_CONFIG_H

#include <stdbool.h>
#include <stdint.h>

#define MELEXIS_REFRESH_CODES 8U          // 0.5 Hz ... 64 Hz, each twice the one before
#define MELEXIS_FILTER_LEVEL_MAX 3U
#define MELEXIS_REFRESH_CODE_DEFAULT 2U   // 2 Hz
#define MELEXIS_FILTER_LEVEL_DEFAULT 0U   // off

typedef struct {
    uint8_t refresh_code;   // 0 = 0.5 Hz, 1 = 1 Hz, 2 = 2 Hz ... 7 = 64 Hz
    uint8_t filter_level;   // 0..MELEXIS_FILTER_LEVEL_MAX
} melexis_config_t;

typedef struct {
    unsigned applied;       // keys that set a field
    unsigned rejected;      // known keys whose value is not allowed (the field kept its value)
    unsigned unknown;       // keys that are not settings of this module
} melexis_config_report_t;

void melexis_config_default(melexis_config_t *cfg);

// True when both fields are inside their limits. A missing configuration is not valid.
bool melexis_config_valid(const melexis_config_t *cfg);

// Frame period in microseconds (2 000 000 at 0.5 Hz down to 15 625 at 64 Hz); 0 for an invalid configuration.
uint32_t melexis_config_period_us(const melexis_config_t *cfg);

// Shortest interval in whole milliseconds a rate limiter may enforce between two frames of this sensor without refusing real ones (at least 1); 0 when invalid.
uint32_t melexis_config_min_interval_ms(const melexis_config_t *cfg);

// Number of frames averaged by the filter: 1, 2, 4 or 8; 0 for an invalid configuration.
uint8_t melexis_config_filter_frames(const melexis_config_t *cfg);

// Reads "refresh_hz=<0.5|1|2|4|8|16|32|64>" and "filter_level=<0..3>" lines from text into cfg and fills report (which may be NULL).
// Returns false only when cfg or text is missing. Nothing is written for a rejected value.
bool melexis_config_apply_text(melexis_config_t *cfg, const char *text, melexis_config_report_t *report);

#endif // MELEXIS_CONFIG_H
