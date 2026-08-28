#!/usr/bin/env bash
# HYDRA_UMC_SCRIPT_STANDARD_HEADER_BEGIN
# *****************************************************************************
# Project   : URTC-VISION-TOOL
# Script    : build_firmware.sh
# Purpose   : Incremental firmware build and versioned artifact packaging workflow.
# Author    : JuanenRac (Electro Hobby 3D)
# Email     : electrohobby3d@gmail.com
# Copyright : (C) 2026 JuanenRac
# License   : GPL-3.0 - see LICENSE
# *****************************************************************************
# HYDRA_UMC_SCRIPT_STANDARD_HEADER_END
# HYDRA_UMC_SCRIPT_STANDARD_BANNER_BEGIN
printf '\n*******************************************************************************\n'
printf '%s\n' "* URTC-VISION-TOOL - build_firmware.sh"
printf '%s\n' "* Mode      : INCREMENTAL BUILD"
printf '%s\n' "* Author    : JuanenRac (Electro Hobby 3D)"
printf '%s\n' "* Email     : electrohobby3d@gmail.com"
printf '%s\n' "* Copyright : (C) 2026 JuanenRac"
printf '%s\n' "* License   : GPL-3.0 - see LICENSE"
printf '%s\n' "* ------------------------------------------------------------------------- *"
printf '%s\n' "* 1. Increment the project version and synchronise its manifest."
printf '%s\n' "* 2. Run this project's declared build, verification and packaging commands."
printf '%s\n' "* 3. Report the result and keep an interactive terminal open."
printf '%s\n' "*******************************************************************************"
printf '\n'
# HYDRA_UMC_SCRIPT_STANDARD_BANNER_END
# URTC-VISION-TOOL - Firmware Build Script: build_firmware.sh
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
    # HYDRA_UMC_SCRIPT_STANDARD_VERSION_STEP
    printf '%s\n' "[1/3] Incrementing project version and synchronising its manifest..."
    # HYDRA_UMC_SCRIPT_STANDARD_VERSION_CAPTURE_BEFORE
    HYDRA_UMC_VERSION_BEFORE="$(python3 -c 'import json, pathlib, sys; print(json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))["version"])' "$(dirname "$0")/hydra-umc.project.json")"
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD="$ROOT/build"
FIRMWARE_OUT="$ROOT/firmware"
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
    python3 "$(dirname "$0")/bump_manifest_version.py" --sync
    # HYDRA_UMC_SCRIPT_STANDARD_VERSION_CAPTURE_AFTER
    HYDRA_UMC_VERSION_AFTER="$(python3 -c 'import json, pathlib, sys; print(json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))["version"])' "$(dirname "$0")/hydra-umc.project.json")"
    printf '\n*******************************************************************************\n'
    printf '%s\n' '* VERSION INCREMENT COMPLETED'
    printf '%s\n' "* v${HYDRA_UMC_VERSION_BEFORE:-unknown} -> v${HYDRA_UMC_VERSION_AFTER:-unknown}"
    printf '%s\n' '* Project manifest synchronized with the firmware version.'
    printf '%s\n' '*******************************************************************************'
    printf '\n'
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
