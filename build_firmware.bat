@echo off
REM HYDRA_UMC_SCRIPT_STANDARD_HEADER_BEGIN
REM *****************************************************************************
REM Project   : URTC-VISION-TOOL
REM Script    : build_firmware.bat
REM Purpose   : Incremental firmware build and versioned artifact packaging workflow.
REM Author    : JuanenRac (Electro Hobby 3D)
REM Email     : electrohobby3d@gmail.com
REM Copyright : (C) 2026 JuanenRac
REM License   : GPL-3.0 - see LICENSE
REM *****************************************************************************
REM HYDRA_UMC_SCRIPT_STANDARD_HEADER_END
REM HYDRA_UMC_SCRIPT_STANDARD_BANNER_BEGIN
echo.
echo *****************************************************************************
echo * URTC-VISION-TOOL - build_firmware.bat
echo * Mode      : INCREMENTAL BUILD
echo * Author    : JuanenRac (Electro Hobby 3D)
echo * Email     : electrohobby3d@gmail.com
echo * Copyright : (C) 2026 JuanenRac
echo * License   : GPL-3.0 - see LICENSE
echo * ------------------------------------------------------------------------- *
echo * 1. Increment the project version and synchronise its manifest.
echo * 2. Run this project's declared build, verification and packaging commands.
echo * 3. Report the result and keep an interactive terminal open.
echo *****************************************************************************
echo.
REM HYDRA_UMC_SCRIPT_STANDARD_BANNER_END
REM URTC-VISION-TOOL - Firmware Build Script
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
REM HYDRA_UMC_SCRIPT_STANDARD_VERSION_STEP
echo [1/3] Incrementing project version and synchronising its manifest...
REM HYDRA_UMC_SCRIPT_STANDARD_VERSION_CAPTURE_BEFORE
for /f "usebackq delims=" %%V in (`python -c "import json; print(json.load(open(r'%~dp0hydra-umc.project.json', encoding='utf-8'))['version'])"`) do set "HYDRA_UMC_VERSION_BEFORE=%%V"
echo.
cd /d "%~dp0"
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
python "%~dp0bump_manifest_version.py" --sync
if errorlevel 1 goto :error
REM HYDRA_UMC_SCRIPT_STANDARD_VERSION_CAPTURE_AFTER
for /f "usebackq delims=" %%V in (`python -c "import json; print(json.load(open(r'%~dp0hydra-umc.project.json', encoding='utf-8'))['version'])"`) do set "HYDRA_UMC_VERSION_AFTER=%%V"
if not defined HYDRA_UMC_VERSION_BEFORE set "HYDRA_UMC_VERSION_BEFORE=unknown"
if not defined HYDRA_UMC_VERSION_AFTER set "HYDRA_UMC_VERSION_AFTER=unknown"
echo.
echo *****************************************************************************
echo * VERSION INCREMENT COMPLETED
echo * v%HYDRA_UMC_VERSION_BEFORE% ^> v%HYDRA_UMC_VERSION_AFTER%
echo * Project manifest synchronized with the firmware version.
echo *****************************************************************************
echo.
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
set "HYDRA_UMC_SCRIPT_RESULT=0"
goto :HYDRA_UMC_SCRIPT_STANDARD_FINISH

:error
echo.
echo BUILD FAILED - see the output above.
set "HYDRA_UMC_SCRIPT_RESULT=1"
goto :HYDRA_UMC_SCRIPT_STANDARD_FINISH

REM HYDRA_UMC_SCRIPT_STANDARD_SAFE_PAUSE
:HYDRA_UMC_SCRIPT_STANDARD_FINISH
if not defined HYDRA_UMC_SCRIPT_RESULT set "HYDRA_UMC_SCRIPT_RESULT=%ERRORLEVEL%"
echo.
echo [INFO] Script completed. Exit code: %HYDRA_UMC_SCRIPT_RESULT%.
pause
exit /b %HYDRA_UMC_SCRIPT_RESULT%
