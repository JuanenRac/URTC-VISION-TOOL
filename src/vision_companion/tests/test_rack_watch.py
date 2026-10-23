# =============================================================================
# URTC-VISION-TOOL - vision_companion tests: test_rack_watch.py
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""The thermal watch of the tool rack over time, against a simulated rack, and the words of the check in eight languages."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from vision_companion import cli, rack_check, rack_text, rack_watch

STATE = {"elapsed_ms": 0, "slots": [
    {"slot": 0, "roi": [0, 0, 60, 60], "occupied": True, "target_c": 200},
    {"slot": 1, "roi": [100, 0, 160, 60], "occupied": True, "target_c": 300},
    {"slot": 2, "roi": [200, 0, 260, 60], "occupied": False, "target_c": 0},
    {"slot": 3, "roi": [300, 0, 360, 60], "occupied": True, "target_c": 0},
]}


def run(scenario: str, count: int = 16, interval_ms: int = 5000) -> dict[int, rack_watch.SlotHistory]:
    frames = rack_watch.simulate(STATE, scenario, count, interval_ms, 640, 480)
    assert frames.shape == (count, 24, 32)
    return {h.slot: h for h in rack_watch.watch(frames, STATE, 640, 480, interval_ms)}


def test_a_healthy_rack_reaches_its_targets_and_may_swap() -> None:
    histories = run("healthy")
    assert histories[0].final == rack_check.REACHED and histories[0].reached_at_ms is not None
    assert histories[1].final == rack_check.REACHED and histories[1].reached_at_ms >= histories[0].reached_at_ms
    assert histories[2].final == rack_check.EMPTY_OK and histories[3].final == rack_check.IDLE_OK
    assert histories[0].swap_state == "swap_ok" and histories[3].swap_state == "swap_ok"


def test_a_swap_has_to_wait_until_the_tip_is_stable() -> None:
    histories = run("healthy", count=4)          # 15 s: the 200 C tip is still short of the target
    assert histories[0].swap_state == "swap_wait" and histories[0].reached_at_ms is None


def test_a_slow_heater_is_a_fault_and_blocks_the_swap() -> None:
    histories = run("slow_heater", count=16)     # 75 s, the allowed time is 60 s
    assert histories[0].final == rack_check.NOT_REACHED and histories[0].swap_state == "swap_blocked"
    assert histories[1].swap_state == "swap_ok"


def test_an_overshoot_is_a_fault_and_blocks_the_swap() -> None:
    histories = run("overshoot")
    assert histories[0].final == rack_check.OVERSHOOT and histories[0].swap_state == "swap_blocked"


def test_a_heater_in_an_empty_slot_is_found_while_it_heats() -> None:
    histories = run("heater_in_empty_slot")
    assert histories[2].final == rack_check.EMPTY_HOT and histories[2].swap_state == "swap_blocked"


def test_a_dead_region_never_allows_a_swap() -> None:
    histories = run("dead_region")
    assert histories[0].final == rack_check.UNKNOWN and histories[0].swap_state == "swap_wait" and histories[0].reached_at_ms is None


def test_the_simulation_is_repeatable_and_noisy_per_seed() -> None:
    a = rack_watch.simulate(STATE, "healthy", 4, 5000, 640, 480, seed=3)
    b = rack_watch.simulate(STATE, "healthy", 4, 5000, 640, 480, seed=3)
    c = rack_watch.simulate(STATE, "healthy", 4, 5000, 640, 480, seed=4)
    assert np.array_equal(a, b) and not np.array_equal(a, c)


@pytest.mark.parametrize("call", [
    lambda: rack_watch.simulate(STATE, "nonsense", 4, 5000, 640, 480),
    lambda: rack_watch.simulate(STATE, "healthy", 0, 5000, 640, 480),
    lambda: rack_watch.simulate({}, "healthy", 4, 5000, 640, 480),
    lambda: rack_watch.simulate({"slots": [{"slot": 0}]}, "healthy", 4, 5000, 640, 480),
    lambda: rack_watch.watch(np.zeros((24, 32)), STATE, 640, 480, 5000),
    lambda: rack_watch.watch(np.zeros((2, 24, 32)), STATE, 640, 480, 0),
])
def test_bad_input_is_refused(call) -> None:
    with pytest.raises(rack_check.RackCheckError):
        call()


def test_every_language_has_every_word() -> None:
    assert rack_text.LANGUAGES == ("en", "es", "de", "fr", "it", "ja", "zh", "pt")
    for lang in rack_text.LANGUAGES:
        assert set(rack_text.TEXTS[lang]) == set(rack_text.KEYS), lang
        assert all(rack_text.TEXTS[lang][k].strip() for k in rack_text.KEYS), lang
    for verdict in (rack_check.UNKNOWN, rack_check.EMPTY_OK, rack_check.EMPTY_HOT, rack_check.IDLE_OK, rack_check.IDLE_HOT,
                    rack_check.HEATING, rack_check.REACHED, rack_check.NOT_REACHED, rack_check.OVERSHOOT):
        assert verdict in rack_text.KEYS
    assert rack_text.text("reached_after", "pt", s="3.0") == "atingido após 3.0 s"
    assert rack_text.text("fault", "xx") == "FAULT"


def test_the_commands_simulate_watch_and_translate(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    state_path, frames_path, out = tmp_path / "s.json", tmp_path / "f.npy", tmp_path / "o.json"
    state_path.write_text(json.dumps(STATE), encoding="utf-8")
    assert cli.main(["rack-simulate", str(state_path), "--scenario", "healthy", "--out", str(frames_path)]) == cli.EXIT_OK
    assert cli.main(["rack-watch", str(state_path), "--frames", str(frames_path), "--out", str(out), "--lang", "es"]) == cli.EXIT_OK
    shown = capsys.readouterr().out
    assert "hueco 0" in shown and "se puede cambiar la herramienta" in shown
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["faults"] == 0 and doc["slots"][0]["swap"] == "swap_ok" and doc["interval_ms"] == 5000
    assert cli.main(["rack-simulate", str(state_path), "--scenario", "overshoot", "--out", str(frames_path)]) == cli.EXIT_OK
    assert cli.main(["rack-watch", str(state_path), "--frames", str(frames_path), "--lang", "ja"]) == cli.EXIT_FINDINGS
    assert "高温すぎる" in capsys.readouterr().out
    assert cli.main(["rack-watch", str(state_path), "--frames", str(tmp_path / "missing.npy")]) == cli.EXIT_BAD_INPUT
    np.save(frames_path, np.zeros((24, 32)))
    assert cli.main(["rack-watch", str(state_path), "--frames", str(frames_path)]) == cli.EXIT_BAD_INPUT
    assert cli.main(["rack-simulate", str(tmp_path / "missing.json"), "--out", str(frames_path)]) == cli.EXIT_BAD_INPUT


def test_rack_check_prints_in_the_chosen_language(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    state_path, frame_path = tmp_path / "s.json", tmp_path / "f.npy"
    state_path.write_text(json.dumps(dict(STATE, elapsed_ms=30_000)), encoding="utf-8")
    frame = np.full((24, 32), 24.0, dtype=np.float32)
    frame[0:3, 10:13] = 90.0
    np.save(frame_path, frame)
    cli.main(["rack-check", str(state_path), "--frame", str(frame_path), "--ambient", "24", "--lang", "de"])
    assert "Fach 2: leer" in capsys.readouterr().out
