// =============================================================================
// URTC-VISION-TOOL Firmware - Shared types, defines, and version identity
// Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
// GPL-3.0 - see LICENSE
// =============================================================================
#ifndef FIRMWARE_COMMON_H
#define FIRMWARE_COMMON_H

#include <stdint.h>

// =============================================================================
// TARGET MCU: STM32 (Cortex-M4F family - exact part TBD, same situation as
// sibling repo URTC-SMART-RACK). No PCB/schematic exists yet for this tool
// head (see hardware/), so
// this firmware and its linker script (STM32_MINIMAL.ld) target the core
// generically rather than guessing a specific flash/RAM size or exact MLX9064x
// / RGB camera wiring that a real schematic hasn't confirmed yet.
//
// Sibling repo URTC (see URTC/src/F303-master/firmware_common.h) follows
// this exact same version-macro pattern for its own STM32F303 boards:
// bumped in place by bump_version.py before every real build, odometer
// carry (PATCH+1, rolling into MINOR past 9). Reused here rather than
// reinvented.
// =============================================================================
#define FIRMWARE_VERSION_MAJOR 0
#define FIRMWARE_VERSION_MINOR 0
#define FIRMWARE_VERSION_PATCH 4

// Encodes MAJOR.MINOR.PATCH as a single monotonically-increasing integer
// (major*10000 + minor*100 + patch) - same convention as URTC's own
// firmware/firmware_manifest.json "version_code" field.
#define FIRMWARE_VERSION_CODE \
    (FIRMWARE_VERSION_MAJOR * 10000u + FIRMWARE_VERSION_MINOR * 100u + FIRMWARE_VERSION_PATCH)

#endif // FIRMWARE_COMMON_H
