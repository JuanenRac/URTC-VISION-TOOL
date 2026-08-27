/* =============================================================================
 * URTC-VISION-TOOL Firmware - Minimal linker script: STM32_MINIMAL.ld
 * Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
 * GPL-3.0 - see LICENSE
 * =============================================================================
 * PLACEHOLDER memory map - there is no real PCB/schematic for
 * URTC-VISION-TOOL yet (see hardware/ and firmware_common.h's own header
 * comment), so the exact STM32 part number, and therefore its real
 * FLASH/RAM sizes, is unknown. The sizes below (128K FLASH / 32K RAM) are
 * a conservative floor a mainstream Cortex-M4F STM32 part ships with (same
 * as sibling repo URTC-SMART-RACK's own STM32G4_MINIMAL.ld) - safe to link
 * and boot into main() on real STM32 silicon, but NOT to be trusted as
 * this board's real flash budget once a specific part is chosen and its
 * real datasheet linker script (mirroring URTC's own
 * src/F303-master/STM32F303CCTx_APP.ld) replaces this file.
 */

MEMORY
{
    FLASH (rx)  : ORIGIN = 0x08000000, LENGTH = 128K
    RAM   (rwx) : ORIGIN = 0x20000000, LENGTH = 32K
}

/* Top of RAM - Reset_Handler's initial stack pointer (startup_stm32_minimal.c). */
_estack = ORIGIN(RAM) + LENGTH(RAM);

SECTIONS
{
    .isr_vector :
    {
        . = ALIGN(4);
        KEEP(*(.isr_vector))
        . = ALIGN(4);
    } > FLASH

    .text :
    {
        . = ALIGN(4);
        *(.text)
        *(.text*)
        *(.rodata)
        *(.rodata*)
        . = ALIGN(4);
    } > FLASH

    /* Load address in FLASH for the initialized-data image Reset_Handler
     * copies into RAM at startup (_sidata..). */
    _sidata = LOADADDR(.data);

    .data :
    {
        . = ALIGN(4);
        _sdata = .;
        *(.data)
        *(.data*)
        . = ALIGN(4);
        _edata = .;
    } > RAM AT> FLASH

    .bss :
    {
        . = ALIGN(4);
        _sbss = .;
        *(.bss)
        *(.bss*)
        *(COMMON)
        . = ALIGN(4);
        _ebss = .;
    } > RAM

    /DISCARD/ :
    {
        *(.ARM.attributes)
        *(.comment)
    }
}
