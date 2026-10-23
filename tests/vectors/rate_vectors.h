// GENERATED from spec by tools/make_extra_vectors.py - do not edit by hand.
// Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
// GPL-3.0-or-later - see LICENSE
#ifndef RATE_VECTORS_H
#define RATE_VECTORS_H

#include <stdint.h>

typedef struct { const char *name; uint32_t min_interval_ms; uint8_t count; uint32_t times_ms[7]; uint8_t allowed[7]; } rate_vec_case_t;

static const rate_vec_case_t RATE_VEC_CASES[] = {
    {"the first message is always accepted", 100u, 1, {0u}, {1}},
    {"inside the interval refused, at the interval accepted", 100u, 7, {0u, 50u, 99u, 100u, 150u, 199u, 200u}, {1, 0, 0, 1, 0, 0, 1}},
    {"a refused message does not move the window", 100u, 5, {1000u, 1099u, 1100u, 1150u, 1200u}, {1, 0, 1, 0, 1}},
    {"an interval of zero accepts everything", 0u, 4, {5u, 5u, 5u, 6u}, {1, 1, 1, 1}},
    {"across the wrap of the millisecond counter", 100u, 4, {4294967280u, 16u, 83u, 84u}, {1, 0, 0, 1}},
    {"the largest interval", 4294967295u, 3, {0u, 4294967294u, 4294967295u}, {1, 0, 1}},
    {"a clock that goes backwards counts as a long time ago", 10u, 2, {1000u, 900u}, {1, 1}},
};

#define RATE_VEC_COUNT(a) ((int)(sizeof(a) / sizeof((a)[0])))

#endif // RATE_VECTORS_H
