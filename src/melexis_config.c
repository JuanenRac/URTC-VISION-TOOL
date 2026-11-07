// =============================================================================
// URTC-VISION-TOOL Firmware - Thermal sensor settings: melexis_config.c
// Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
// GPL-3.0-or-later - see LICENSE
// =============================================================================
#include "melexis_config.h"

#include <stddef.h>
#include <string.h>

static const uint32_t k_period_us[MELEXIS_REFRESH_CODES] = {2000000U, 1000000U, 500000U, 250000U, 125000U, 62500U, 31250U, 15625U};

void melexis_config_default(melexis_config_t *cfg)
{
    if (cfg == NULL) {
        return;
    }
    cfg->refresh_code = MELEXIS_REFRESH_CODE_DEFAULT;
    cfg->filter_level = MELEXIS_FILTER_LEVEL_DEFAULT;
}

bool melexis_config_valid(const melexis_config_t *cfg)
{
    return cfg != NULL && cfg->refresh_code < MELEXIS_REFRESH_CODES && cfg->filter_level <= MELEXIS_FILTER_LEVEL_MAX;
}

uint32_t melexis_config_period_us(const melexis_config_t *cfg)
{
    return melexis_config_valid(cfg) ? k_period_us[cfg->refresh_code] : 0U;
}

uint32_t melexis_config_min_interval_ms(const melexis_config_t *cfg)
{
    uint32_t period = melexis_config_period_us(cfg);
    if (period == 0U) {
        return 0U;
    }
    period /= 1000U;
    return period == 0U ? 1U : period;
}

uint8_t melexis_config_filter_frames(const melexis_config_t *cfg)
{
    return melexis_config_valid(cfg) ? (uint8_t)(1U << cfg->filter_level) : 0U;
}

// "0.5" -> 0, "1" -> 1 ... "64" -> 7; -1 for anything else (a sign, a space inside, a second dot, "01", "2.0").
static int refresh_code_from_text(const char *s, size_t len)
{
    static const char *const names[MELEXIS_REFRESH_CODES] = {"0.5", "1", "2", "4", "8", "16", "32", "64"};
    for (unsigned i = 0; i < MELEXIS_REFRESH_CODES; i++) {
        if (strlen(names[i]) == len && memcmp(names[i], s, len) == 0) {
            return (int)i;
        }
    }
    return -1;
}

static int filter_level_from_text(const char *s, size_t len)
{
    if (len == 1U && s[0] >= '0' && s[0] <= '3') {
        return s[0] - '0';
    }
    return -1;
}

static bool is_blank(char c)
{
    return c == ' ' || c == '\t' || c == '\r';
}

bool melexis_config_apply_text(melexis_config_t *cfg, const char *text, melexis_config_report_t *report)
{
    melexis_config_report_t local = {0U, 0U, 0U};
    if (cfg == NULL || text == NULL) {
        if (report != NULL) {
            *report = local;
        }
        return false;
    }
    const char *p = text;
    while (*p != '\0') {
        const char *end = strchr(p, '\n');
        size_t line_len = end != NULL ? (size_t)(end - p) : strlen(p);
        const char *line = p;
        p += line_len + (end != NULL ? 1U : 0U);
        while (line_len > 0U && is_blank(*line)) {
            line++;
            line_len--;
        }
        while (line_len > 0U && is_blank(line[line_len - 1U])) {
            line_len--;
        }
        if (line_len == 0U || line[0] == '#') {
            continue;
        }
        const char *eq = memchr(line, '=', line_len);
        if (eq == NULL) {
            local.unknown++;
            continue;
        }
        size_t key_len = (size_t)(eq - line);
        const char *value = eq + 1;
        size_t value_len = line_len - key_len - 1U;
        while (key_len > 0U && is_blank(line[key_len - 1U])) {
            key_len--;
        }
        while (value_len > 0U && is_blank(*value)) {
            value++;
            value_len--;
        }
        if (key_len == 10U && memcmp(line, "refresh_hz", 10U) == 0) {
            int code = refresh_code_from_text(value, value_len);
            if (code < 0) {
                local.rejected++;
            } else {
                cfg->refresh_code = (uint8_t)code;
                local.applied++;
            }
        } else if (key_len == 12U && memcmp(line, "filter_level", 12U) == 0) {
            int level = filter_level_from_text(value, value_len);
            if (level < 0) {
                local.rejected++;
            } else {
                cfg->filter_level = (uint8_t)level;
                local.applied++;
            }
        } else {
            local.unknown++;
        }
    }
    if (report != NULL) {
        *report = local;
    }
    return true;
}
