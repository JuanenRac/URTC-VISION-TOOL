// =============================================================================
// URTC-VISION-TOOL Firmware - Virtual sensor link: the real receive path behind a text port
// Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
// GPL-3.0-or-later - see LICENSE
// =============================================================================
// The modules the vision head receives the thermal sensor with (receive ring, frame assembly with resynchronisation, frame layer, reading validation, freshness,
// rate limiter, diagnostics, silence watch) joined the way the main loop of the board joins them, compiled for the host, behind a text port: one command per line
// on standard input, one line per accepted reading on standard output. A script (tools/sensor_bench.py) plays scenarios through it, with faults.
//
// Input lines (hexadecimal values, no 0x, except the clock which is decimal):
//   T <ms>        the clock is now <ms> (never goes back); runs the silence watch
//   S <bytes>     bytes arrive from the sensor, one after the other with the main loop polling after each
//   B <bytes>     the same bytes arrive in one burst before the main loop polls (the receive ring can overflow)
//   Q             print the counters
//   M <text>      print the line  M <text>  (a marker that tells where the answer to one command ends)
// Output lines:
//   R <centidegrees>   an accepted reading (decimal, signed)
//   Q <frame_errors> <out_of_range> <malformed> <rate_limited> <unsupported> <replay> <stale> <disconnects> <accepted_gap_ms> <overflow> <timeouts> <silent>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "../src/rate_limiter.h"
#include "../src/sensor_diagnostics.h"
#include "../src/sensor_freshness.h"
#include "../src/sensor_rx.h"
#include "../src/vision_sensor_link.h"

#define LINE_MAX_CHARS 4096
#define MIN_INTERVAL_MS 50u        // the least time between two accepted readings
#define SILENCE_TIMEOUT_MS 1000u   // a sensor that sends nothing accepted for this long is reported silent

static sensor_rx_t rx;
static rate_limiter_t limiter;
static sensor_freshness_t freshness;
static sensor_diagnostics_t diagnostics;
static uint32_t now_ms;

static int hex_digit(char c)
{
    if (c >= '0' && c <= '9') {
        return c - '0';
    }
    if (c >= 'a' && c <= 'f') {
        return c - 'a' + 10;
    }
    if (c >= 'A' && c <= 'F') {
        return c - 'A' + 10;
    }
    return -1;
}

static int parse_bytes(const char *text, uint8_t *out, int max)
{
    int count = 0;
    while (*text != '\0') {
        if (*text == ' ' || *text == '\t' || *text == '\r' || *text == '\n') {
            text++;
            continue;
        }
        const int high = hex_digit(text[0]);
        const int low = high < 0 ? -1 : hex_digit(text[1]);
        if (high < 0 || low < 0 || count >= max) {
            return -1;
        }
        out[count++] = (uint8_t)(high * 16 + low);
        text += 2;
    }
    return count;
}

static void poll_sensor(void)
{
    sensor_thermal_reading_t reading;
    while (sensor_rx_poll(&rx, &limiter, &freshness, &diagnostics, now_ms, &reading)) {
        printf("R %d\n", (int)reading.temp_centidegrees_c);
    }
}

static void print_counters(void)
{
    rx.overflow_bytes += urtc_ring_take_dropped(&rx.ring);
    printf("Q %u %u %u %u %u %u %u %u %u %u %u %u\n", (unsigned)diagnostics.frame_errors, (unsigned)diagnostics.out_of_range_count, (unsigned)diagnostics.malformed_payload_count,
           (unsigned)diagnostics.rate_limited_count, (unsigned)diagnostics.unsupported_sensor_count, (unsigned)diagnostics.replay_count, (unsigned)diagnostics.stale_count,
           (unsigned)diagnostics.disconnect_count, (unsigned)diagnostics.last_interarrival_ms, (unsigned)rx.overflow_bytes, (unsigned)rx.timeouts, diagnostics.silent ? 1u : 0u);
}

static bool handle(char *line)
{
    uint8_t bytes[LINE_MAX_CHARS / 2];
    unsigned value = 0;
    switch (line[0]) {
        case 'T':
            if (sscanf(line + 1, "%u", &value) == 1 && value >= now_ms) {
                now_ms = value;
                (void)vision_sensor_link_tick(&freshness, &diagnostics, now_ms, SILENCE_TIMEOUT_MS);
                poll_sensor();
                return true;
            }
            return false;
        case 'S':
        case 'B': {
            const int count = parse_bytes(line + 1, bytes, (int)sizeof bytes);
            if (count < 0) {
                return false;
            }
            for (int i = 0; i < count; i++) {
                (void)sensor_rx_on_byte(&rx, bytes[i]);
                if (line[0] == 'S') {
                    poll_sensor();
                }
            }
            poll_sensor();
            return true;
        }
        case 'M':
            printf("M %s", line + 2);
            return true;
        case 'Q':
            print_counters();
            return true;
        default:
            return false;
    }
}

int main(void)
{
    sensor_rx_init(&rx);
    rate_limiter_init(&limiter, MIN_INTERVAL_MS);
    sensor_freshness_init(&freshness);
    sensor_diagnostics_init(&diagnostics);
    char line[LINE_MAX_CHARS];
    while (fgets(line, sizeof line, stdin) != NULL) {
        if (line[0] == '\n' || line[0] == '\r' || line[0] == '#') {
            continue;
        }
        if (!handle(line)) {
            printf("E %s", line);
            if (strchr(line, '\n') == NULL) {
                printf("\n");
            }
        }
        (void)fflush(stdout);
    }
    return 0;
}
