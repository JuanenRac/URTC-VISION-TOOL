#!/usr/bin/env bash
# =============================================================================
# URTC-VISION-TOOL - Firmware Build Script: build_firmware.sh
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0 - see LICENSE
# =============================================================================
# Compiles this project's minimal Cortex-M4F skeleton (src/main.c +
# src/startup_stm32_minimal.c, see those files' own header comments for
# why there's no ST HAL/CMSIS dependency yet - no real PCB exists to pin
# down the exact STM32 part). Same arm-none-eabi-gcc toolchain as sibling
# repos URTC/build_firmware.sh and URTC-SMART-RACK/build_firmware.sh,
# reused rather than reinvented, but with the HAL/CMSIS fetch steps
# skipped entirely - there's no chip-specific vendor code to fetch yet at
# this project's current andamiaje (scaffolding) stage.
#
# This builds the FIRMWARE side only. The vision-side companion (Python,
# runs on a host/CM5, not on the STM32) lives in src/vision_companion/ -
# see that directory's own README for its build/run instructions.
#
# Usage:
#   chmod +x build_firmware.sh   (one-time)
#   ./build_firmware.sh
set -e
HYDRA_UMC_CI_MODE="${HYDRA_UMC_CI:-0}"
if [ "$HYDRA_UMC_CI_MODE" = "1" ]; then
    echo "URTC-VISION-TOOL CI: version sources are read-only."
else
    python3 "$(dirname "$0")/bump_manifest_version.py" || exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD="$ROOT/build"
FIRMWARE_OUT="$ROOT/firmware"

echo "============================================================================="
echo " URTC-VISION-TOOL - firmware build"
echo ""
echo " Compiles the minimal Cortex-M4F skeleton (no ST HAL yet - see"
echo " src/firmware_common.h for why) with arm-none-eabi-gcc."
echo ""
echo " Author:  JuanenRac (Electro Hobby 3D) - electrohobby3d@gmail.com"
echo " License: GPL-3.0 - see LICENSE"
echo "============================================================================="

if [ -t 0 ]; then
    trap 'echo ""; read -r -p "Press Enter to close this window..." _' EXIT
fi

echo ""
echo "=== 1. Toolchain ==="
if ! command -v arm-none-eabi-gcc >/dev/null 2>&1; then
    echo "FAIL: arm-none-eabi-gcc not found. Install the ARM GNU Toolchain"
    echo "      (e.g. 'choco install gcc-arm-embedded' on Windows, or"
    echo "      'apt install gcc-arm-none-eabi' on Debian/Ubuntu), then re-run."
    exit 1
fi
echo "  OK   arm-none-eabi-gcc found: $(arm-none-eabi-gcc --version | head -1)"

echo ""
echo "=== 2. Version bump (odometer, see bump_version.py) ==="
# bump_version.py prints exactly "MAJOR.MINOR.PATCH" to stdout on success -
# captured directly instead of re-parsing the header back out.
if [ "$HYDRA_UMC_CI_MODE" = "1" ]; then
    VERSION="$(grep -oE 'define[[:space:]]+FIRMWARE_VERSION_MAJOR[[:space:]]+[0-9]+' src/firmware_common.h | grep -oE '[0-9]+$').$(grep -oE 'define[[:space:]]+FIRMWARE_VERSION_MINOR[[:space:]]+[0-9]+' src/firmware_common.h | grep -oE '[0-9]+$').$(grep -oE 'define[[:space:]]+FIRMWARE_VERSION_PATCH[[:space:]]+[0-9]+' src/firmware_common.h | grep -oE '[0-9]+$')"
else
    VERSION="$(python3 bump_version.py src/firmware_common.h FIRMWARE_VERSION)"
fi
echo "  Firmware version: $VERSION"

echo ""
echo "=== 3. Compile + link ==="
mkdir -p "$BUILD" "$FIRMWARE_OUT"

CFLAGS="-mcpu=cortex-m4 -mthumb -mfloat-abi=hard -mfpu=fpv4-sp-d16 -ffreestanding -fno-builtin -Wall -Wextra -O2 -g -Isrc"
LDFLAGS="-T src/STM32_MINIMAL.ld -nostdlib -Wl,--gc-sections -Wl,-Map=$BUILD/urtc-vision-tool.map"

arm-none-eabi-gcc $CFLAGS -c src/startup_stm32_minimal.c -o "$BUILD/startup_stm32_minimal.o"
arm-none-eabi-gcc $CFLAGS -c src/main.c -o "$BUILD/main.o"
arm-none-eabi-gcc $CFLAGS $LDFLAGS "$BUILD/startup_stm32_minimal.o" "$BUILD/main.o" -o "$BUILD/urtc-vision-tool.elf"
echo "  OK   Linked $BUILD/urtc-vision-tool.elf"

arm-none-eabi-objcopy -O binary "$BUILD/urtc-vision-tool.elf" "$BUILD/urtc-vision-tool.bin"
arm-none-eabi-objcopy -O ihex "$BUILD/urtc-vision-tool.elf" "$BUILD/urtc-vision-tool.hex"
echo "  OK   $BUILD/urtc-vision-tool.bin / .hex"

echo ""
echo "=== 4. Size report ==="
arm-none-eabi-size "$BUILD/urtc-vision-tool.elf"

echo ""
echo "=== 5. Publish versioned artifacts to firmware/ ==="
cp "$BUILD/urtc-vision-tool.elf" "$FIRMWARE_OUT/URTC_VISION_TOOL_FIRMWARE_v${VERSION}.elf"
cp "$BUILD/urtc-vision-tool.bin" "$FIRMWARE_OUT/URTC_VISION_TOOL_FIRMWARE_v${VERSION}.bin"
cp "$BUILD/urtc-vision-tool.hex" "$FIRMWARE_OUT/URTC_VISION_TOOL_FIRMWARE_v${VERSION}.hex"
echo "  OK   firmware/URTC_VISION_TOOL_FIRMWARE_v${VERSION}.{elf,bin,hex}"

echo ""
echo "============================================================================="
echo " Build complete - v${VERSION}"
echo "============================================================================="
