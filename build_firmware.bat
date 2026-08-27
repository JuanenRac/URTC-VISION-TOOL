@echo off
REM =============================================================================
REM URTC-VISION-TOOL - Firmware Build Script
REM Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
REM GPL-3.0 - see LICENSE
REM =============================================================================
REM Compiles this project's minimal Cortex-M4F skeleton (src/main.c +
REM src/startup_stm32_minimal.c - see those files' own header comments for
REM why there's no ST HAL/CMSIS dependency yet, no real PCB exists to pin
REM down the exact STM32 part). Same arm-none-eabi-gcc toolchain as sibling
REM repos URTC/build_firmware.bat and URTC-SMART-RACK/build_firmware.bat,
REM reused rather than reinvented, but with the HAL/CMSIS fetch steps
REM skipped entirely - nothing chip-specific to fetch yet at this
REM project's current andamiaje (scaffolding) stage.
REM
REM This builds the FIRMWARE side only. The vision-side companion (Python,
REM runs on a host/CM5, not on the STM32) lives in src\vision_companion\ -
REM see that directory's own README for its build/run instructions.
setlocal enabledelayedexpansion
python "%~dp0bump_manifest_version.py"
if errorlevel 1 ( echo VERSION BUMP FAILED. & pause & exit /b 1 )
cd /d "%~dp0"

echo =============================================================================
echo  URTC-VISION-TOOL - firmware build
echo.
echo  Compiles the minimal Cortex-M4F skeleton (no ST HAL yet - see
echo  src/firmware_common.h for why) with arm-none-eabi-gcc.
echo.
echo  Author:  JuanenRac (Electro Hobby 3D) - electrohobby3d@gmail.com
echo  License: GPL-3.0 - see LICENSE
echo =============================================================================
echo.

echo === 1. Toolchain ===
where arm-none-eabi-gcc >nul 2>nul
if errorlevel 1 (
    echo FAIL: arm-none-eabi-gcc not found. Install the ARM GNU Toolchain
    echo       (e.g. "choco install gcc-arm-embedded"^), then re-run.
    goto :error
)
echo   OK   arm-none-eabi-gcc found
echo.

echo === 2. Version bump (odometer, see bump_version.py) ===
for /f "delims=" %%V in ('python bump_version.py src\firmware_common.h FIRMWARE_VERSION') do set VERSION=%%V
if "%VERSION%"=="" goto :error
echo   Firmware version: %VERSION%
echo.

echo === 3. Compile + link ===
if not exist build mkdir build
if not exist firmware mkdir firmware

set CFLAGS=-mcpu=cortex-m4 -mthumb -mfloat-abi=hard -mfpu=fpv4-sp-d16 -ffreestanding -fno-builtin -Wall -Wextra -O2 -g -Isrc
set LDFLAGS=-T src\STM32_MINIMAL.ld -nostdlib -Wl,--gc-sections -Wl,-Map=build\urtc-vision-tool.map

arm-none-eabi-gcc %CFLAGS% -c src\startup_stm32_minimal.c -o build\startup_stm32_minimal.o
if errorlevel 1 goto :error
arm-none-eabi-gcc %CFLAGS% -c src\main.c -o build\main.o
if errorlevel 1 goto :error
arm-none-eabi-gcc %CFLAGS% %LDFLAGS% build\startup_stm32_minimal.o build\main.o -o build\urtc-vision-tool.elf
if errorlevel 1 goto :error
echo   OK   Linked build\urtc-vision-tool.elf

arm-none-eabi-objcopy -O binary build\urtc-vision-tool.elf build\urtc-vision-tool.bin
arm-none-eabi-objcopy -O ihex build\urtc-vision-tool.elf build\urtc-vision-tool.hex
echo   OK   build\urtc-vision-tool.bin / .hex
echo.

echo === 4. Size report ===
arm-none-eabi-size build\urtc-vision-tool.elf
echo.

echo === 5. Publish versioned artifacts to firmware\ ===
copy /y build\urtc-vision-tool.elf firmware\URTC_VISION_TOOL_FIRMWARE_v%VERSION%.elf >nul
copy /y build\urtc-vision-tool.bin firmware\URTC_VISION_TOOL_FIRMWARE_v%VERSION%.bin >nul
copy /y build\urtc-vision-tool.hex firmware\URTC_VISION_TOOL_FIRMWARE_v%VERSION%.hex >nul
echo   OK   firmware\URTC_VISION_TOOL_FIRMWARE_v%VERSION%.{elf,bin,hex}
echo.

echo =============================================================================
echo  Build complete - v%VERSION%
echo =============================================================================
exit /b 0

:error
echo.
echo BUILD FAILED - see the output above.
exit /b 1
