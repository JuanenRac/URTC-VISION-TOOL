# =============================================================================
# URTC-VISION-TOOL - vision_companion tests: test_rack_check.py
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""The thermal check of the tool rack, and the false colour of this program against the shared vectors."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from vision_companion import cli, rack_check
from vision_companion.cli import thermal_to_false_color

FIXTURES = Path(__file__).resolve().parent / "fixtures"
RACK = json.loads((FIXTURES / "rack_vectors.json").read_text(encoding="utf-8"))
THERMAL = json.loads((FIXTURES / "thermal_vectors.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", RACK["verify"], ids=lambda c: c["name"])
def test_the_verdicts_are_those_of_the_shared_cases(case) -> None:
    assert rack_check.verify_slot(case["occupied"], case["commanded_c"], case["measured_c"], case["ambient_c"], case["elapsed_ms"]) == case["verdict"]


@pytest.mark.parametrize("case", THERMAL["false_color"], ids=lambda c: c["name"])
def test_the_false_colour_matches_the_shared_vectors_within_one_level(case) -> None:
    frame = np.array([[np.nan if v is None else v for v in row] for row in case["frame"]], dtype=np.float32)
    rng = tuple(case["range"]) if case["range"] else None
    image = thermal_to_false_color(frame, rng)
    height, width = frame.shape
    small = image.resize((width, height), resample=0)        # the program draws every pixel 16 times as large
    got = np.asarray(small, dtype=np.int16).reshape(-1)
    want = np.frombuffer(bytes.fromhex(case["rgb"]), dtype=np.uint8).astype(np.int16)
    assert got.shape == want.shape
    assert np.max(np.abs(got - want)) <= 1


def frame_with_hot_spots() -> np.ndarray:
    frame = np.full((24, 32), 24.0, dtype=np.float32)
    frame[0:3, 0:3] = 195.0       # slot 0: region (0,0)-(60,60) of the RGB image
    frame[0:3, 5:8] = 120.0       # slot 1
    frame[0:3, 10:13] = 90.0      # slot 2, empty
    frame[0:3, 15:18] = 24.0      # slot 3, told to stay cold
    return frame


STATE = {"elapsed_ms": 30_000, "slots": [
    {"slot": 0, "roi": [0, 0, 60, 60], "occupied": True, "target_c": 200},
    {"slot": 1, "roi": [100, 0, 160, 60], "occupied": True, "target_c": 300},
    {"slot": 2, "roi": [200, 0, 260, 60], "occupied": False, "target_c": 0},
    {"slot": 3, "roi": [300, 0, 360, 60], "occupied": True, "target_c": 0},
]}


def test_each_slot_is_judged_from_its_region() -> None:
    results = {r.slot: r for r in rack_check.check_rack(frame_with_hot_spots(), STATE, 640, 480)}
    assert results[0].verdict == rack_check.REACHED and not results[0].is_fault
    assert results[1].verdict == rack_check.HEATING and not results[1].is_fault
    assert results[2].verdict == rack_check.EMPTY_HOT and results[2].is_fault
    assert results[3].verdict == rack_check.IDLE_OK


def test_a_slow_tip_becomes_a_fault_after_the_allowed_time() -> None:
    late = dict(STATE, elapsed_ms=61_000)
    results = {r.slot: r for r in rack_check.check_rack(frame_with_hot_spots(), late, 640, 480)}
    assert results[1].verdict == rack_check.NOT_REACHED and results[1].is_fault


def test_a_region_outside_the_sensor_has_no_reading_and_is_never_a_pass() -> None:
    state = {"elapsed_ms": 0, "slots": [{"slot": 0, "roi": [700, 0, 760, 60], "occupied": True, "target_c": 200}]}
    result = rack_check.check_rack(frame_with_hot_spots(), state, 640, 480)[0]
    assert result.verdict == rack_check.UNKNOWN and result.measured_c is None


@pytest.mark.parametrize("state", [None, {}, {"slots": [{"slot": 0}]}, {"slots": [{"slot": 0, "roi": [5, 5, 1, 1], "occupied": True}]}, {"slots": [], "elapsed_ms": -1},
                                    {"slots": [], "elapsed_ms": True}])
def test_a_bad_state_is_refused(state) -> None:
    with pytest.raises(rack_check.RackCheckError):
        rack_check.check_rack(frame_with_hot_spots(), state, 640, 480)


def test_the_command_reports_and_exits_with_the_findings_code(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    state_path, frame_path, out = tmp_path / "s.json", tmp_path / "f.npy", tmp_path / "o.json"
    state_path.write_text(json.dumps(STATE), encoding="utf-8")
    np.save(frame_path, frame_with_hot_spots())
    code = cli.main(["rack-check", str(state_path), "--frame", str(frame_path), "--ambient", "24", "--out", str(out)])
    assert code == cli.EXIT_FINDINGS
    assert "slot 2: empty" in capsys.readouterr().out
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["faults"] == 1 and doc["slots"][2]["verdict"] == "heater_in_empty_slot" and doc["ambient_c"] == 24.0
    clean = dict(STATE, slots=[STATE["slots"][0]])
    state_path.write_text(json.dumps(clean), encoding="utf-8")
    assert cli.main(["rack-check", str(state_path), "--frame", str(frame_path)]) == cli.EXIT_OK
    assert cli.main(["rack-check", str(tmp_path / "missing.json")]) == cli.EXIT_BAD_INPUT
