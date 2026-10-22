<!-- =============================================================================
URTC-VISION-TOOL - Hardware notes
Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
GPL-3.0-or-later - see LICENSE
============================================================================= -->

# Hardware

There is **no hardware design for this tool head yet**: no schematic, no PCB layout, no
Gerber files, no case and no confirmed microcontroller part or sensor wiring. This folder is
the place where those files will go once they exist.

What is decided so far, all of it provisional:

- the target family is a Cortex-M4F STM32; the exact part, and therefore its flash and RAM
  sizes, is open (the linker script assumes a conservative floor);
- the thermal sensor is an MLX9064x: 32x24 pixels for the MLX90640 and MLX90642, 16x12 for the
  MLX90641 (the companion handles both shapes);
- the RGB camera and its interface are not chosen;
- the thermal data reaches a host through the CAN messages of URTC's thermal inspection tool (tool
  profile 22, identifiers `0x250`-`0x255`, see URTC's `docs/CANBUS.TXT`); this head does not define a
  second protocol for the image.

Nothing in `src/` has ever read a real sensor or driven a real pin.
