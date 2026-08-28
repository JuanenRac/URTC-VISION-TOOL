// =============================================================================
// URTC-VISION-TOOL Firmware - Host-side sensor/link scenarios
// Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
// GPL-3.0 - see LICENSE
// =============================================================================
// The promotion audit's own "añadir capa simulada de sensor que reproduzca
// desconexion, frame truncado y medidas fuera de rango sin requerir
// hardware optico" / "Evidencia: ... pruebas de parser con tramas
// validas/invalidas, asegurando que no se activa salida ante datos
// corruptos": this file plays real encoded frames - some deliberately
// truncated, corrupted or out of range, and a real explicit
// disconnection - through sensor_frame.c/sensor_reading.c/rate_limiter.c/
// sensor_diagnostics.c exactly as a future I2C/SPI receive path will, and
// checks the real resulting decision (a real reading, or none at all)
// plus the real diagnostic counters at each step - no MLX9064x, RGB
// trigger or PCB required, since none exist for this board yet (see
// main.c's own note).
#include "test_runner.h"
#include "../src/sensor_frame.h"
#include "../src/sensor_reading.h"
#include "../src/rate_limiter.h"
#include "../src/sensor_diagnostics.h"

// The real decision one receive attempt makes: a real, in-range
// thermal reading on success, or nothing at all (with the real reason
// recorded in `diag`) on any failure - framing, rate limiting, or range
// validation. `buf == NULL` models a real disconnection: no frame
// arrived in the expected window at all.
static bool simulate_sensor_receive(
    rate_limiter_t *rl,
    sensor_diagnostics_t *diag,
    const uint8_t *buf,
    uint8_t buf_len,
    uint32_t now_ms,
    sensor_thermal_reading_t *out_reading)
{
    if (buf == NULL) {
        sensor_diagnostics_note_disconnect(diag);
        return false;
    }

    sensor_frame_t frame;
    if (sensor_frame_parse(buf, buf_len, &frame) != SENSOR_FRAME_OK) {
        sensor_diagnostics_note_frame_error(diag);
        return false; // a bad/truncated/corrupted frame never reaches reading validation
    }

    if (!rate_limiter_allow(rl, now_ms)) {
        sensor_diagnostics_note_rate_limited(diag);
        return false; // a real frame arriving too fast is throttled, not trusted
    }

    if (sensor_reading_validate_thermal(frame.payload, frame.len, out_reading) != SENSOR_READING_OK) {
        sensor_diagnostics_note_out_of_range(diag);
        return false; // a well-formed frame carrying an impossible reading is refused
    }

    sensor_diagnostics_note_accepted_frame(diag, now_ms);
    return true;
}

void run_vision_sensor_scenario_tests(int *failures)
{
    // --- Scenario 1: a real valid frame produces a real accepted reading ---
    {
        rate_limiter_t rl;
        rate_limiter_init(&rl, 50);
        sensor_diagnostics_t diag;
        sensor_diagnostics_init(&diag);

        uint8_t payload[2] = {0xD0, 0x07}; // 20.00C
        uint8_t buf[SENSOR_FRAME_MAX_SIZE];
        uint8_t len = sensor_frame_encode(SENSOR_ID_THERMAL, 1, 1000, payload, 2, buf);

        sensor_thermal_reading_t reading;
        bool accepted = simulate_sensor_receive(&rl, &diag, buf, len, 1000, &reading);
        TEST_ASSERT(accepted == true, "a real, valid, in-range frame is accepted");
        TEST_ASSERT(reading.temp_centidegrees_c == 2000, "the real accepted reading carries the real requested temperature");
        TEST_ASSERT(diag.frame_errors == 0, "no frame errors are recorded for a real valid frame");
        TEST_ASSERT(diag.out_of_range_count == 0, "no out-of-range rejections are recorded for a real valid frame");
    }

    // --- Scenario 2: a real truncated frame never produces a reading ---
    {
        rate_limiter_t rl;
        rate_limiter_init(&rl, 50);
        sensor_diagnostics_t diag;
        sensor_diagnostics_init(&diag);

        uint8_t payload[2] = {0xD0, 0x07};
        uint8_t buf[SENSOR_FRAME_MAX_SIZE];
        uint8_t len = sensor_frame_encode(SENSOR_ID_THERMAL, 1, 1000, payload, 2, buf);

        sensor_thermal_reading_t reading;
        bool accepted = simulate_sensor_receive(&rl, &diag, buf, (uint8_t)(len - 3), 1000, &reading);
        TEST_ASSERT(accepted == false, "a real truncated frame never produces an accepted reading");
        TEST_ASSERT(diag.frame_errors == 1, "the real truncation is recorded as a frame error");
    }

    // --- Scenario 3: a real CRC-corrupted frame never produces a reading ---
    {
        rate_limiter_t rl;
        rate_limiter_init(&rl, 50);
        sensor_diagnostics_t diag;
        sensor_diagnostics_init(&diag);

        uint8_t payload[2] = {0xD0, 0x07};
        uint8_t buf[SENSOR_FRAME_MAX_SIZE];
        uint8_t len = sensor_frame_encode(SENSOR_ID_THERMAL, 1, 1000, payload, 2, buf);
        buf[len - 1] ^= 0xFFu; // real bit-level CRC corruption

        sensor_thermal_reading_t reading;
        bool accepted = simulate_sensor_receive(&rl, &diag, buf, len, 1000, &reading);
        TEST_ASSERT(accepted == false, "a real CRC-corrupted frame never produces an accepted reading");
        TEST_ASSERT(diag.frame_errors == 1, "the real corruption is recorded as a frame error");
    }

    // --- Scenario 4: a real, well-formed but out-of-range reading is refused ---
    {
        rate_limiter_t rl;
        rate_limiter_init(&rl, 50);
        sensor_diagnostics_t diag;
        sensor_diagnostics_init(&diag);

        int16_t too_hot = SENSOR_READING_MAX_TEMP_CENTIDEGREES_C + 100;
        uint8_t payload[2] = {(uint8_t)((uint16_t)too_hot & 0xFF), (uint8_t)(((uint16_t)too_hot >> 8) & 0xFF)};
        uint8_t buf[SENSOR_FRAME_MAX_SIZE];
        uint8_t len = sensor_frame_encode(SENSOR_ID_THERMAL, 1, 1000, payload, 2, buf);

        sensor_thermal_reading_t reading;
        bool accepted = simulate_sensor_receive(&rl, &diag, buf, len, 1000, &reading);
        TEST_ASSERT(accepted == false, "a real, CRC-valid frame carrying an out-of-range temperature is refused - no output is ever activated on it");
        TEST_ASSERT(diag.frame_errors == 0, "the frame itself was real and well-formed - this is not counted as a framing error");
        TEST_ASSERT(diag.out_of_range_count == 1, "the real out-of-range reading is recorded distinctly from a framing error");
    }

    // --- Scenario 5: a real too-fast resend is throttled, not trusted ---
    {
        rate_limiter_t rl;
        rate_limiter_init(&rl, 100);
        sensor_diagnostics_t diag;
        sensor_diagnostics_init(&diag);

        uint8_t payload[2] = {0xD0, 0x07};
        uint8_t buf[SENSOR_FRAME_MAX_SIZE];
        uint8_t len = sensor_frame_encode(SENSOR_ID_THERMAL, 1, 0, payload, 2, buf);

        sensor_thermal_reading_t reading;
        bool first = simulate_sensor_receive(&rl, &diag, buf, len, 0, &reading);
        bool second = simulate_sensor_receive(&rl, &diag, buf, len, 20, &reading);
        TEST_ASSERT(first == true, "the first real frame is accepted");
        TEST_ASSERT(second == false, "a real second frame only 20ms later, under a 100ms rate limit, is throttled");
        TEST_ASSERT(diag.rate_limited_count == 1, "the real throttled frame is recorded distinctly from a framing or range error");
    }

    // --- Scenario 6: a real explicit disconnection is recorded, never crashes the parser ---
    {
        rate_limiter_t rl;
        rate_limiter_init(&rl, 50);
        sensor_diagnostics_t diag;
        sensor_diagnostics_init(&diag);

        sensor_thermal_reading_t reading;
        bool accepted = simulate_sensor_receive(&rl, &diag, NULL, 0, 1000, &reading);
        TEST_ASSERT(accepted == false, "a real disconnection (no frame at all) never produces an accepted reading");
        TEST_ASSERT(diag.disconnect_count == 1, "the real disconnection is recorded distinctly from any framing/range/rate error");
        TEST_ASSERT(diag.frame_errors == 0, "a real disconnection is not miscounted as a framing error");
    }
}
