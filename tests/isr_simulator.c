// =============================================================================
// URTC-VISION-TOOL Firmware - interrupt simulator for the receive path: isr_simulator.c
// Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
// GPL-3.0-or-later - see LICENSE
// =============================================================================
// A host program with its own main(). The receive interrupt of the sensor link does not exist yet, so this plays it with the thing that is closest to
// one on a host: a POSIX signal. A timer delivers SIGALRM many times a second; the handler does what the real interrupt handler is allowed to do, which
// is call sensor_rx_on_byte() with the next byte of a stream, and nothing else. The main loop meanwhile runs sensor_rx_poll() flat out, so the handler
// preempts it at any instruction, in the middle of a ring operation included, exactly as an interrupt preempts the main loop on the chip.
//
// What it checks: with a handler that keeps pace the main loop hands over every good frame of the stream, in order, and loses no byte; with a handler
// that floods a slow main loop the ring overflows and says so, and still nothing but a real frame of the stream ever comes out as a reading (never a
// half-updated or invented one); the diagnostics and the rate limiter are only ever touched by the main loop, so a reading of them between two polls
// is always a whole snapshot (UVIS-BUG-016 asks for exactly that split).
//
// Linux only: elsewhere the program says it was skipped and succeeds. To hunt data races as well, build it by hand with -fsanitize=thread (the signal
// handler is not a second thread, so the thread sanitizer sees one thread; use it for the ring's own atomics through tests that call it from two threads).
#define _GNU_SOURCE
#include <stdint.h>
#include <stdio.h>

#include "test_runner.h"

#if defined(__linux__)

#include <signal.h>
#include <stdbool.h>
#include <string.h>
#include <sys/time.h>
#include <time.h>

#include "../src/rate_limiter.h"
#include "../src/sensor_diagnostics.h"
#include "../src/sensor_frame.h"
#include "../src/sensor_freshness.h"
#include "../src/sensor_rx.h"

#define FRAMES 200u
#define STREAM_MAX (FRAMES * (SENSOR_FRAME_MAX_SIZE + 6u))

static uint8_t stream[STREAM_MAX];
static unsigned stream_len;
static volatile unsigned stream_pos;        // written only by the handler
static volatile unsigned burst_max = 1u;    // bytes the handler delivers per signal
static unsigned lcg = 12345u;
static sensor_rx_t rx;

static unsigned next_random(void)
{
    lcg = lcg * 1103515245u + 12345u;
    return (lcg >> 16) & 0x7FFFu;
}

// The "interrupt": the only thing it does is put bytes in the ring.
static void on_alarm(int signo)
{
    (void)signo;
    unsigned n = 1u + next_random() % burst_max;
    while (n-- && stream_pos < stream_len) {
        (void)sensor_rx_on_byte(&rx, stream[stream_pos]);
        stream_pos = stream_pos + 1u;
    }
}

// FRAMES good frames (reading 2000 + number, so the number can be read back), a few bytes of noise between some of them and a bad CRC on every twentieth.
static unsigned build_stream(unsigned *good)
{
    unsigned pos = 0u, ok = 0u;
    uint8_t buf[SENSOR_FRAME_MAX_SIZE];
    for (unsigned i = 0u; i < FRAMES; i++) {
        if (i % 7u == 3u) {
            stream[pos++] = 0x00u;
            stream[pos++] = (uint8_t)(0x40u + i % 5u);
        }
        const int16_t centi = (int16_t)(2000 + (int)i);
        const uint8_t payload[2] = {(uint8_t)((uint16_t)centi >> 8), (uint8_t)((uint16_t)centi & 0xFFu)};
        const uint8_t len = sensor_frame_encode(SENSOR_ID_THERMAL, (uint8_t)i, (i + 1u) * 100u, payload, 2, buf);
        if (i % 20u == 19u) {
            buf[len - 1u] ^= 0x55u;               // a damaged frame: it must be counted and must never become a reading
        } else {
            ok++;
        }
        memcpy(&stream[pos], buf, len);
        pos += len;
    }
    *good = ok;
    return pos;
}

static uint32_t now_ms(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint32_t)(ts.tv_sec * 1000u + (unsigned)ts.tv_nsec / 1000000u);
}

typedef struct {
    unsigned accepted;
    int last_number;
    int out_of_order;
    int impossible;
    unsigned snapshots_bad;
    uint32_t frame_errors;
} outcome_t;

// Runs one round: starts the timer, polls until the whole stream was delivered and the ring is empty, stops the timer.
static outcome_t play(unsigned burst, unsigned pause_us, long timer_us)
{
    outcome_t out = {0u, -1, 0, 0, 0u, 0u};
    rate_limiter_t rl;
    sensor_freshness_t fresh;
    sensor_diagnostics_t diag;
    sensor_rx_init(&rx);
    rate_limiter_init(&rl, 0);
    sensor_freshness_init(&fresh);
    sensor_diagnostics_init(&diag);
    stream_pos = 0u;
    burst_max = burst;

    struct sigaction sa;
    memset(&sa, 0, sizeof sa);
    sa.sa_handler = on_alarm;
    sigemptyset(&sa.sa_mask);
    sigaction(SIGALRM, &sa, NULL);
    struct itimerval timer = {{0, timer_us}, {0, timer_us}};
    setitimer(ITIMER_REAL, &timer, NULL);

    for (;;) {
        const bool delivered = stream_pos >= stream_len;     // read BEFORE the poll: a poll that finds nothing after this drained everything
        sensor_thermal_reading_t reading;
        if (sensor_rx_poll(&rx, &rl, &fresh, &diag, now_ms(), &reading)) {
            const int number = (int)reading.temp_centidegrees_c - 2000;
            if (number < 0 || number >= (int)FRAMES || number % 20 == 19) {
                out.impossible++;                  // a reading no good frame of the stream carried
            } else if (number <= out.last_number) {
                out.out_of_order++;
            }
            out.last_number = number;
            out.accepted++;
            // the diagnostics are read here, between two polls, as the main loop would to report them: a whole snapshot
            if (!diag.has_last_accept_ms || diag.silent) {
                out.snapshots_bad++;
            }
        } else if (delivered) {
            break;
        }
        if (pause_us != 0u) {
            struct timespec nap = {0, (long)pause_us * 1000L};
            nanosleep(&nap, NULL);
        }
    }
    struct itimerval stop = {{0, 0}, {0, 0}};
    setitimer(ITIMER_REAL, &stop, NULL);
    out.frame_errors = diag.frame_errors;
    return out;
}

int main(void)
{
    int failures_value = 0;
    int *failures = &failures_value;
    unsigned good = 0u;
    stream_len = build_stream(&good);

    // A handler that keeps pace (at most two bytes per signal against a main loop that never sleeps): every good frame, in order, no byte lost.
    outcome_t paced = play(2u, 0u, 200);
    TEST_ASSERT(paced.accepted == good, "a handler that keeps pace: every good frame of the stream becomes a reading");
    TEST_ASSERT(paced.out_of_order == 0 && paced.impossible == 0, "in order, and never a reading that no frame carried");
    TEST_ASSERT(rx.overflow_bytes == 0u, "and the ring never lost a byte");
    TEST_ASSERT(paced.snapshots_bad == 0u, "the diagnostics read between two polls are a whole snapshot");
    TEST_ASSERT(paced.frame_errors >= FRAMES / 20u, "and every damaged frame was counted by the main loop");

    // A flood (up to 48 bytes per signal) against a main loop that naps two milliseconds between polls: the ring overflows and says so, and what comes out is still real.
    outcome_t flood = play(48u, 2000u, 300);
    TEST_ASSERT(flood.impossible == 0 && flood.out_of_order == 0, "a flood never produces an invented or a repeated reading");
    TEST_ASSERT(rx.overflow_bytes > 0u, "the flood overflows the ring and the receiver counts the bytes it lost");
    TEST_ASSERT(flood.accepted < good, "so frames are lost, not guessed");

    if (failures_value == 0) {
        printf("All tests passed.\n");
        return 0;
    }
    printf("%d test(s) failed.\n", failures_value);
    return 1;
}

#else

int main(void)
{
    printf("SKIP: the interrupt simulator needs POSIX signals (Linux).\n");
    return 0;
}

#endif
