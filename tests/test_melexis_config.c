// =============================================================================
// URTC-VISION-TOOL Firmware - tests for melexis_config.c
// Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
// GPL-3.0-or-later - see LICENSE
// =============================================================================
#include <stdio.h>

#include "test_runner.h"
#include "../src/melexis_config.h"

void run_melexis_config_tests(int *failures)
{
    melexis_config_t cfg;
    melexis_config_report_t r;

    melexis_config_default(&cfg);
    TEST_ASSERT(cfg.refresh_code == 2U && cfg.filter_level == 0U, "the defaults are 2 Hz and the filter off");
    TEST_ASSERT(melexis_config_valid(&cfg), "the defaults are valid");
    TEST_ASSERT(melexis_config_period_us(&cfg) == 500000U, "2 Hz is a 500 ms period");
    TEST_ASSERT(melexis_config_min_interval_ms(&cfg) == 500U, "the shortest interval at 2 Hz is 500 ms");
    TEST_ASSERT(melexis_config_filter_frames(&cfg) == 1U, "the filter off averages one frame");

    // Every refresh rate, from 0.5 Hz to 64 Hz, each twice the one before.
    static const char *const rates[] = {"0.5", "1", "2", "4", "8", "16", "32", "64"};
    static const uint32_t periods[] = {2000000U, 1000000U, 500000U, 250000U, 125000U, 62500U, 31250U, 15625U};
    static const uint32_t intervals[] = {2000U, 1000U, 500U, 250U, 125U, 62U, 31U, 15U};
    for (unsigned i = 0; i < 8U; i++) {
        char text[32];
        snprintf(text, sizeof text, "refresh_hz=%s\n", rates[i]);
        melexis_config_default(&cfg);
        melexis_config_apply_text(&cfg, text, &r);
        TEST_ASSERT(r.applied == 1U && r.rejected == 0U && cfg.refresh_code == i, "every supported rate is accepted");
        TEST_ASSERT(melexis_config_period_us(&cfg) == periods[i], "the period follows the rate");
        TEST_ASSERT(melexis_config_min_interval_ms(&cfg) == intervals[i], "the shortest interval follows the rate");
    }
    TEST_ASSERT(melexis_config_period_us(&cfg) * 2U == 31250U, "64 Hz is half the period of 32 Hz");

    // Every filter level.
    for (unsigned level = 0; level <= 3U; level++) {
        char text[32];
        snprintf(text, sizeof text, "filter_level=%u", level);
        melexis_config_default(&cfg);
        melexis_config_apply_text(&cfg, text, &r);
        TEST_ASSERT(r.applied == 1U && cfg.filter_level == level, "every filter level is accepted (also on the last line without a newline)");
        TEST_ASSERT(melexis_config_filter_frames(&cfg) == (1U << level), "the filter averages 1, 2, 4 or 8 frames");
    }

    // Values that are not allowed are never used and never rounded to a neighbour.
    static const char *const bad_rates[] = {"3", "0", "128", "0.25", "2.0", "02", "-2", "+2", "1e1", "two", "", " ", "2 4", "0,5", "64.", ".5"};
    for (unsigned i = 0; i < sizeof bad_rates / sizeof bad_rates[0]; i++) {
        char text[48];
        snprintf(text, sizeof text, "refresh_hz=%s\n", bad_rates[i]);
        melexis_config_default(&cfg);
        melexis_config_apply_text(&cfg, text, &r);
        TEST_ASSERT(r.rejected == 1U && r.applied == 0U && cfg.refresh_code == MELEXIS_REFRESH_CODE_DEFAULT, "a rate that is not supported is rejected and the field keeps its value");
    }
    static const char *const bad_levels[] = {"4", "9", "-1", "+1", "00", "01", "1.0", "x", "", "10", "255"};
    for (unsigned i = 0; i < sizeof bad_levels / sizeof bad_levels[0]; i++) {
        char text[48];
        snprintf(text, sizeof text, "filter_level=%s\n", bad_levels[i]);
        melexis_config_default(&cfg);
        melexis_config_apply_text(&cfg, text, &r);
        TEST_ASSERT(r.rejected == 1U && r.applied == 0U && cfg.filter_level == MELEXIS_FILTER_LEVEL_DEFAULT, "a filter level outside 0..3 is rejected and the field keeps its value");
    }

    // A rejected value does not undo an earlier good one on the same field.
    melexis_config_default(&cfg);
    melexis_config_apply_text(&cfg, "refresh_hz=16\nrefresh_hz=17\n", &r);
    TEST_ASSERT(cfg.refresh_code == 5U && r.applied == 1U && r.rejected == 1U, "a later bad value leaves the earlier good one in place");
    melexis_config_apply_text(&cfg, "refresh_hz=4\nrefresh_hz=8\n", &r);
    TEST_ASSERT(cfg.refresh_code == 4U && r.applied == 2U, "the last good value wins");

    // Layout of the text.
    melexis_config_default(&cfg);
    melexis_config_apply_text(&cfg, "# the thermal sensor\n\n  refresh_hz = 8  \r\n\tfilter_level=3\t\n", &r);
    TEST_ASSERT(cfg.refresh_code == 4U && cfg.filter_level == 3U && r.applied == 2U && r.rejected == 0U && r.unknown == 0U, "comments, blank lines, spaces, tabs and CRLF are tolerated");
    melexis_config_default(&cfg);
    melexis_config_apply_text(&cfg, "#refresh_hz=64\n", &r);
    TEST_ASSERT(cfg.refresh_code == 2U && r.applied == 0U && r.unknown == 0U, "a commented line is not read");
    melexis_config_apply_text(&cfg, "gain=3\nrefresh_hz\nREFRESH_HZ=8\nrefresh_hz_x=8\n=8\nfilter=2\n", &r);
    TEST_ASSERT(r.unknown == 6U && r.applied == 0U && cfg.refresh_code == 2U, "keys that are not settings (wrong case, longer, missing, no name) are counted and ignored");
    melexis_config_apply_text(&cfg, "", &r);
    TEST_ASSERT(r.applied == 0U && r.rejected == 0U && r.unknown == 0U, "empty text changes nothing");

    // Missing arguments fail closed.
    TEST_ASSERT(!melexis_config_apply_text(NULL, "refresh_hz=8", &r) && r.applied == 0U, "no configuration: false and an empty report");
    TEST_ASSERT(!melexis_config_apply_text(&cfg, NULL, &r), "no text: false");
    TEST_ASSERT(melexis_config_apply_text(&cfg, "refresh_hz=8", NULL), "a NULL report is allowed");
    TEST_ASSERT(!melexis_config_valid(NULL), "no configuration is not valid");
    TEST_ASSERT(melexis_config_period_us(NULL) == 0U && melexis_config_min_interval_ms(NULL) == 0U && melexis_config_filter_frames(NULL) == 0U, "no configuration gives 0 everywhere");
    melexis_config_default(NULL);

    // A structure that was filled by something else is judged, not trusted.
    melexis_config_t odd = {8U, 0U};
    TEST_ASSERT(!melexis_config_valid(&odd) && melexis_config_period_us(&odd) == 0U, "a rate code of 8 is not valid");
    odd.refresh_code = 7U;
    odd.filter_level = 4U;
    TEST_ASSERT(!melexis_config_valid(&odd) && melexis_config_filter_frames(&odd) == 0U && melexis_config_min_interval_ms(&odd) == 0U, "a filter level of 4 is not valid");
    odd.filter_level = 3U;
    TEST_ASSERT(melexis_config_valid(&odd) && melexis_config_min_interval_ms(&odd) == 15U, "the largest valid configuration is 64 Hz with 8 frames");
}
