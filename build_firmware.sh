#!/usr/bin/env bash
# HYDRA_UMC_SCRIPT_STANDARD_HEADER_BEGIN
# *****************************************************************************
# Project   : URTC-VISION-TOOL
# Script    : build_firmware.sh
# Purpose   : Incremental firmware build and versioned artifact packaging workflow.
# Author    : JuanenRac (Electro Hobby 3D)
# Email     : electrohobby3d@gmail.com
# Copyright : (C) 2026 JuanenRac
# License   : GPL-3.0-or-later - see LICENSE
# *****************************************************************************
# HYDRA_UMC_SCRIPT_STANDARD_HEADER_END
# HYDRA_UMC_SCRIPT_STANDARD_BANNER_BEGIN
printf '\n*******************************************************************************\n'
printf '%s\n' "* URTC-VISION-TOOL - build_firmware.sh"
printf '%s\n' "* Mode      : BUILD (no version change)"
printf '%s\n' "* Author    : JuanenRac (Electro Hobby 3D)"
printf '%s\n' "* Email     : electrohobby3d@gmail.com"
printf '%s\n' "* Copyright : (C) 2026 JuanenRac"
printf '%s\n' "* License   : GPL-3.0-or-later - see LICENSE"
printf '%s\n' "* ------------------------------------------------------------------------- *"
printf '%s\n' "* 1. Read the project version (compiling never changes it; run bump.py to raise it)."
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
URTC_CI_MODE="${URTC_CI:-0}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Every path below is relative to the repository root, whatever the directory the script is started from.
cd "$ROOT"
BUILD="$ROOT/build"
FIRMWARE_OUT="$ROOT/firmware"
if [ "$URTC_CI_MODE" = "1" ]; then
    echo "URTC-VISION-TOOL CI: version sources are read-only."
    # Release mode writes the images to firmware/ (git-ignored, published only
    # as assets of the GitHub release - see tools/publish_release_assets.py);
    # CI mode writes them under build/ and touches no tracked file.
    FIRMWARE_OUT="$BUILD/firmware"
else
    # HYDRA_UMC_SCRIPT_STANDARD_VERSION_STEP
    printf '%s\n' "[1/3] Reading the project version (compiling never changes it; raise it with bump.py first)..."
    # HYDRA_UMC_SCRIPT_STANDARD_VERSION_CAPTURE_BEFORE
    HYDRA_UMC_VERSION_BEFORE="$(python3 -c 'import json, pathlib, sys; print(json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))["version"])' "$ROOT/urtc.project.json")"
fi

# The files a version bump rewrites. They are copied aside before the bump and
# put back if anything fails afterwards, so a build that does not produce an
# image never leaves a newer version, manifest or changelog behind.
VERSION_FILES="src/firmware_common.h urtc.project.json CHANGELOG.md"
VERSION_BACKUP="$BUILD/version_backup"
VERSION_BUMPED=0
on_exit() {
    status=$?
    if [ "$VERSION_BUMPED" = "1" ] && [ "$status" -ne 0 ]; then
        for f in $VERSION_FILES; do
            cp -f "$VERSION_BACKUP/$f" "$ROOT/$f"
        done
        echo "Build failed: version, manifest and changelog restored to their previous state."
    fi
    if [ -t 0 ]; then
        echo ""
        read -r -p "Press Enter to close this window..." _ || true
    fi
}
trap on_exit EXIT

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
echo "=== 2. Real logic tests (host gcc, not arm-none-eabi-gcc) ==="
HOST_CC="${CC:-cc}"
if ! command -v "$HOST_CC" >/dev/null 2>&1; then
    HOST_CC=gcc
fi
if ! command -v "$HOST_CC" >/dev/null 2>&1; then
    echo "FAIL: no host C compiler found (tried \$CC and gcc)."
    exit 1
fi
mkdir -p "$BUILD"
# URTC_SANITIZE=1 (set by CI) builds the host tests with AddressSanitizer and UBSan.
SANITIZE_FLAGS=""
if [ "${URTC_SANITIZE:-0}" = "1" ]; then
    SANITIZE_FLAGS="-fsanitize=address,undefined -fno-sanitize-recover=undefined"
fi
"$HOST_CC" -std=c11 -Wall -Wextra -Wconversion -Isrc -Itests $SANITIZE_FLAGS \
    -o "$BUILD/host_tests" \
    tests/test_main.c tests/test_sensor_frame.c tests/test_sensor_reading.c tests/test_rate_limiter.c tests/test_sensor_diagnostics.c tests/test_vision_sensor_scenarios.c tests/test_robustness.c tests/test_sensor_freshness.c tests/test_sensor_vectors.c \
    src/sensor_frame.c src/sensor_reading.c src/rate_limiter.c src/sensor_diagnostics.c src/vision_sensor_link.c src/sensor_freshness.c
"$BUILD/host_tests"
echo "  OK   sensor_frame.c / sensor_reading.c / rate_limiter.c / sensor_freshness.c / sensor_diagnostics.c / vision_sensor_link.c pure-logic tests passed"

echo ""
echo "=== 2b. Build tooling tests (version odometer boundaries) ==="
python3 -m unittest discover -s tests -p "test_*.py"
echo "  OK   build tooling tests passed"

echo ""
echo "=== 3. Firmware version (read from the header; bump.py raises it, building never does) ==="
# Compiling never changes the version: it is read from the header. Raise it first
# with "python3 bump.py".
VERSION="$(grep -oE 'define[[:space:]]+FIRMWARE_VERSION_MAJOR[[:space:]]+[0-9]+' src/firmware_common.h | grep -oE '[0-9]+$').$(grep -oE 'define[[:space:]]+FIRMWARE_VERSION_MINOR[[:space:]]+[0-9]+' src/firmware_common.h | grep -oE '[0-9]+$').$(grep -oE 'define[[:space:]]+FIRMWARE_VERSION_PATCH[[:space:]]+[0-9]+' src/firmware_common.h | grep -oE '[0-9]+$')"
echo "  Firmware version: $VERSION"

echo ""
echo "=== 4. Compile + link ==="
mkdir -p "$BUILD" "$FIRMWARE_OUT"

CFLAGS="-mcpu=cortex-m4 -mthumb -mfloat-abi=hard -mfpu=fpv4-sp-d16 -ffreestanding -fno-builtin -ffunction-sections -fdata-sections -Wall -Wextra -Wconversion -O2 -g -Isrc"
LDFLAGS="-T src/STM32_MINIMAL.ld -nostdlib -Wl,--gc-sections -Wl,-Map=$BUILD/urtc-vision-tool.map"

# Every module is compiled for the Cortex-M4F target, not only the two that the
# image links today: a warning or a missing C-library function in a logic module
# shows up now and not on the day the board exists.
mkdir -p "$BUILD/arm"
for source in src/*.c; do
    arm-none-eabi-gcc $CFLAGS -c "$source" -o "$BUILD/arm/$(basename "$source" .c).o"
done
echo "  OK   every src/*.c compiled for Cortex-M4F"

arm-none-eabi-gcc $CFLAGS $LDFLAGS "$BUILD/arm/startup_stm32_minimal.o" "$BUILD/arm/main.o" -o "$BUILD/urtc-vision-tool.elf"
echo "  OK   Linked $BUILD/urtc-vision-tool.elf"

# All modules must also resolve against each other without a C library; this
# link is only a check and produces no image.
arm-none-eabi-gcc $CFLAGS -T src/STM32_MINIMAL.ld -nostdlib -Wl,--gc-sections "$BUILD"/arm/*.o -o "$BUILD/all-modules-check.elf"
echo "  OK   all modules link together without a C library"

arm-none-eabi-objcopy -O binary "$BUILD/urtc-vision-tool.elf" "$BUILD/urtc-vision-tool.bin"
arm-none-eabi-objcopy -O ihex "$BUILD/urtc-vision-tool.elf" "$BUILD/urtc-vision-tool.hex"
echo "  OK   $BUILD/urtc-vision-tool.bin / .hex"

echo ""
echo "=== 5. Size report ==="
arm-none-eabi-size "$BUILD/urtc-vision-tool.elf"

echo ""
echo "=== 6. Write versioned artifacts to firmware/ (git-ignored) ==="
cp "$BUILD/urtc-vision-tool.elf" "$FIRMWARE_OUT/URTC_VISION_TOOL_FIRMWARE_v${VERSION}.elf"
cp "$BUILD/urtc-vision-tool.bin" "$FIRMWARE_OUT/URTC_VISION_TOOL_FIRMWARE_v${VERSION}.bin"
cp "$BUILD/urtc-vision-tool.hex" "$FIRMWARE_OUT/URTC_VISION_TOOL_FIRMWARE_v${VERSION}.hex"
echo "  OK   firmware/URTC_VISION_TOOL_FIRMWARE_v${VERSION}.{elf,bin,hex}"

echo ""
echo "============================================================================="
echo " Build complete - v${VERSION}"
echo "============================================================================="
