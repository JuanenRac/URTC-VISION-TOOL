// =============================================================================
// URTC-VISION-TOOL Firmware - Minimal Cortex-M4F startup: startup_stm32_minimal.c
// Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
// GPL-3.0 - see LICENSE
// =============================================================================
// Hand-written vector table + reset entry, standing in for ST's own
// CMSIS/HAL startup code until a real PCB pins down the exact STM32 part
// (see firmware_common.h and STM32_MINIMAL.ld's own header comments for
// why - identical situation and identical file to sibling repo
// URTC-SMART-RACK's own startup_stm32g4_minimal.c, copied rather than
// reinvented). Every Cortex-M4F part shares the same 15 core exception
// vectors (defined below, per ARM's architecture reference manual - not
// chip-specific); the peripheral interrupt slots after them ARE
// chip-specific and unknown without real hardware, so this reserves a
// conservative 32-entry placeholder block instead of guessing a real
// peripheral IRQ layout - safe to link and boot into main(), but NOT a
// substitute for ST's real startup code once actual peripherals
// (MLX9064x thermal sensor, RGB camera trigger, CAN transceiver) get
// wired up and their IRQs matter.
#include <stdint.h>

extern uint32_t _sidata;   // Start of .data initializer in FLASH (from linker script)
extern uint32_t _sdata;    // Start of .data in RAM
extern uint32_t _edata;    // End of .data in RAM
extern uint32_t _sbss;     // Start of .bss in RAM
extern uint32_t _ebss;     // End of .bss in RAM
extern uint32_t _estack;   // Initial stack pointer (top of RAM, from linker script)

extern int main(void);

void Reset_Handler(void);
static void Default_Handler(void);

void NMI_Handler(void)          __attribute__((weak, alias("Default_Handler")));
void HardFault_Handler(void)    __attribute__((weak, alias("Default_Handler")));
void MemManage_Handler(void)    __attribute__((weak, alias("Default_Handler")));
void BusFault_Handler(void)     __attribute__((weak, alias("Default_Handler")));
void UsageFault_Handler(void)   __attribute__((weak, alias("Default_Handler")));
void SVC_Handler(void)          __attribute__((weak, alias("Default_Handler")));
void DebugMon_Handler(void)     __attribute__((weak, alias("Default_Handler")));
void PendSV_Handler(void)       __attribute__((weak, alias("Default_Handler")));
void SysTick_Handler(void)      __attribute__((weak, alias("Default_Handler")));
void IRQ_Placeholder_Handler(void) __attribute__((weak, alias("Default_Handler")));

// Reserve 32 generic external-interrupt slots - a conservative placeholder
// until the real STM32 part (and therefore its real peripheral IRQ table)
// is known. See this file's own header comment.
#define PLACEHOLDER_IRQ_COUNT 32

typedef void (*vector_entry)(void);

// Placed in its own .isr_vector section by the linker script, at the very
// start of FLASH - the address the Cortex-M4F core reads on reset to find
// the initial stack pointer (word 0) and the reset entry point (word 1).
__attribute__((section(".isr_vector"), used))
const vector_entry g_vector_table[16 + PLACEHOLDER_IRQ_COUNT] = {
    (vector_entry)&_estack,     // 0:  Initial stack pointer
    Reset_Handler,              // 1:  Reset
    NMI_Handler,                // 2:  NMI
    HardFault_Handler,          // 3:  Hard fault
    MemManage_Handler,          // 4:  MPU fault
    BusFault_Handler,           // 5:  Bus fault
    UsageFault_Handler,         // 6:  Usage fault
    0, 0, 0, 0,                 // 7-10: Reserved
    SVC_Handler,                // 11: SVCall
    DebugMon_Handler,           // 12: Debug monitor
    0,                          // 13: Reserved
    PendSV_Handler,             // 14: PendSV
    SysTick_Handler,            // 15: SysTick
    // 16..16+PLACEHOLDER_IRQ_COUNT-1: generic placeholder external IRQs -
    // real peripheral assignment lands once the real MCU part is chosen.
    [16 ... 16 + PLACEHOLDER_IRQ_COUNT - 1] = IRQ_Placeholder_Handler,
};

/**
 * Reset entry point - the very first code the core runs. Copies the
 * initialized-data image from FLASH into RAM, zeroes .bss, then hands off
 * to main(). No clock/peripheral bring-up here (SystemInit equivalent) -
 * that's genuinely chip-specific and deferred until real hardware exists,
 * same reasoning as the placeholder IRQ table above.
 */
void Reset_Handler(void)
{
    uint32_t *src = &_sidata;
    uint32_t *dst = &_sdata;
    while (dst < &_edata) {
        *dst++ = *src++;
    }

    dst = &_sbss;
    while (dst < &_ebss) {
        *dst++ = 0;
    }

    main();

    // main() is not expected to return in a real firmware image, but
    // park here instead of falling off the end of FLASH if it ever does.
    for (;;) {
    }
}

/**
 * Catch-all for any exception/interrupt without a real handler yet. Spins
 * forever rather than returning into undefined behavior - a debugger
 * breaking in here with the fault/IRQ number on the stack is exactly the
 * intended diagnostic once real peripherals exist to trigger one.
 */
static void Default_Handler(void)
{
    for (;;) {
    }
}
