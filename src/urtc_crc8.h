// =============================================================================
// URTC-COMMON - firmware_base/urtc_crc8.h
// Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
// GPL-3.0-or-later - see LICENSE
// =============================================================================
// The 8-bit checksum of the serial frames of the tool rack and of the vision sensor link, and of the
// fault recorder records: polynomial 0x07, start value 0x00, bits taken most significant first,
// no final XOR (CRC-8/SMBUS). The check value of the ASCII text "123456789" is 0xF4.
//
// One definition for the repositories that carry it: they copy this file with
// `python tools/vendor_copy.py sync TARGET --set firmware_base` and a test of each one checks the
// copy against the vectors of URTC-COMMON. Header only, so no build list has to change.
#ifndef URTC_CRC8_H
#define URTC_CRC8_H

#include <stdint.h>

#define URTC_CRC8_POLYNOMIAL 0x07u
#define URTC_CRC8_START      0x00u

static inline uint8_t urtc_crc8_update(uint8_t crc, uint8_t byte)
{
    crc ^= byte;
    for (uint8_t bit = 0; bit < 8u; bit++) {
        if (crc & 0x80u) {
            crc = (uint8_t)(((unsigned)crc << 1) ^ URTC_CRC8_POLYNOMIAL);
        } else {
            crc = (uint8_t)(crc << 1);
        }
    }
    return crc;
}

static inline uint8_t urtc_crc8(const uint8_t *data, uint8_t len)
{
    uint8_t crc = URTC_CRC8_START;
    for (uint8_t i = 0; i < len; i++) {
        crc = urtc_crc8_update(crc, data[i]);
    }
    return crc;
}

#endif // URTC_CRC8_H
