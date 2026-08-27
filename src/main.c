// =============================================================================
// URTC-VISION-TOOL Firmware - Application entry point: main.c
// Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
// GPL-3.0 - see LICENSE
// =============================================================================
// STARTING POINT ONLY - proves the ARM Cortex-M4F toolchain (same
// arm-none-eabi-gcc used by sibling repos URTC/src/F303-master and
// URTC-SMART-RACK) actually compiles and links a real firmware image for
// this tool head, not the dual-modal (thermal + RGB) sensor fusion logic
// described in the README yet. There is no real PCB/schematic for
// URTC-VISION-TOOL to date (see hardware/), so this firmware has nothing
// to drive - no MLX9064x I2C link, no RGB camera trigger, no CAN
// transceiver. That real work lands once hardware exists - see
// SONNET/URTC-VISION-TOOL/mejoras_futuras.txt. The vision-side companion
// that DOES run today lives in src/vision_companion/ (Python) - see its
// own README/main.py.
#include "firmware_common.h"

// Read by a debugger/reset inspection without needing a CAN link (this
// board has no confirmed CAN wiring yet - see firmware_common.h) - kept
// `volatile` so the compiler can never optimize it away even though
// nothing in this minimal image reads it back yet.
volatile uint32_t g_firmware_version_code = FIRMWARE_VERSION_CODE;

// Free-running counter incremented in the main loop below - the simplest
// possible proof-of-life a debugger or future watchdog can observe
// without any peripheral driver existing yet.
static volatile uint32_t g_heartbeat;

int main(void)
{
    for (;;) {
        g_heartbeat++;
    }
}
