# =============================================================================
# URTC-VISION-TOOL - tests/test_damaged_input.py
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""Files cut short, saved by a Windows editor or filled in by hand with the wrong kind of value, and the noise a serial
adapter puts around its frames: each ends in a message, never in a traceback."""
from __future__ import annotations

import json
import sys
import types

import numpy as np
import pytest

from vision_companion import cli, inspection, rack_check, rack_watch, slcan_link
from vision_companion.calibration import CalibrationError, load_calibration

PLAN = {"schema": 1, "profile": {"rules": {"r": {"max_c": 90}}},
        "components": [{"ref": "R1", "kind": "r", "roi": [0, 0, 10, 10]}]}
STATE = {"elapsed_ms": 0, "slots": [{"slot": 1, "roi": [0, 0, 40, 40], "occupied": True, "target_c": 100}]}


def _write(path, data, encoding="utf-8"):
    path.write_text(json.dumps(data), encoding=encoding)
    return str(path)


def _bad_frames(tmp_path):
    empty = tmp_path / "empty.npy"
    empty.write_bytes(b"")
    whole = tmp_path / "whole.npy"
    np.save(whole, np.zeros((24, 32), dtype=np.float32))
    cut = tmp_path / "cut.npy"
    cut.write_bytes(whole.read_bytes()[:150])
    header = tmp_path / "header.npy"
    header.write_bytes(whole.read_bytes()[:5])
    archive = tmp_path / "archive.npz"
    np.savez(archive, a=np.zeros((24, 32)))
    words = tmp_path / "words.npy"
    np.save(words, np.array([["a", "b"], ["c", "d"]]))
    return [empty, cut, header, archive, words]


def test_a_frame_file_that_cannot_be_used_is_a_message_in_every_command(tmp_path, capsys):
    plan = _write(tmp_path / "plan.json", PLAN)
    state = _write(tmp_path / "state.json", STATE)
    for frame in _bad_frames(tmp_path):
        for argv in (["inspect", plan, "--frame", str(frame)],
                     ["rack-check", state, "--frame", str(frame)],
                     ["rack-watch", state, "--frames", str(frame), "--interval-ms", "100"],
                     ["drift-check", "--frames", str(frame), str(tmp_path / "base.json"), "--update"]):
            assert cli.main(argv) == cli.EXIT_BAD_INPUT, (argv[0], frame.name)
            assert "error:" in capsys.readouterr().err


@pytest.mark.parametrize("change", [
    {"profile": {"rules": [1]}},
    {"profile": {"rules": "r"}},
    {"components": 5},
    {"components": {"R1": {}}},
])
def test_an_inspection_plan_with_the_wrong_kind_of_value_is_a_plan_error(change):
    with pytest.raises(inspection.PlanError):
        inspection.plan_from_dict({**PLAN, **change})


@pytest.mark.parametrize("slot", [
    {"slot": float("inf")},
    {"target_c": float("inf")},
    {"occupied": "false"},      # a text is always "true": it must be refused, not believed
    {"occupied": None},
])
def test_a_rack_state_with_a_wrong_value_is_refused(slot):
    state = {"elapsed_ms": 0, "slots": [{**STATE["slots"][0], **slot}]}
    with pytest.raises(rack_check.RackCheckError):
        rack_check.check_rack(np.zeros((24, 32), dtype=np.float32), state, 640, 480)


@pytest.mark.parametrize("slots", [[5], ["x"], [{"slot": 1, "roi": [0, 0, 4, 4], "occupied": True, "target_c": "hot"}]])
def test_the_simulation_of_a_wrong_rack_state_is_refused(slots):
    with pytest.raises(rack_check.RackCheckError):
        rack_watch.simulate({"slots": slots}, "healthy", 3, 100, 640, 480)


def test_files_saved_with_a_byte_order_mark_are_read(tmp_path, capsys):
    plan = _write(tmp_path / "plan.json", PLAN, "utf-8-sig")
    state = _write(tmp_path / "state.json", STATE, "utf-8-sig")
    cal = _write(tmp_path / "cal.json", {"schema": 1, "offset_c": 1.0}, "utf-8-sig")
    assert load_calibration(cal).offset_c == 1.0
    assert rack_check.load_state(state)["slots"]
    assert cli.main(["inspect", plan, "--calibration", cal]) != cli.EXIT_BAD_INPUT
    capsys.readouterr()


def test_a_calibration_in_another_encoding_is_a_calibration_error(tmp_path):
    path = tmp_path / "cal.json"
    path.write_text('{"schema": 1}', encoding="utf-16")
    with pytest.raises(CalibrationError):
        load_calibration(path)


def test_the_bell_of_a_refused_command_and_the_time_stamp_do_not_lose_a_frame():
    for line in ("\at1601AA", "t1601AA1F3C", "\a\at1601AA\n"):
        message = slcan_link.parse_line(line)
        assert message is not None and (message.arbitration_id, message.data) == (0x160, b"\xaa"), repr(line)
    for line in ("t1601AAFF", "t1602AA", "t9001AA"):
        assert slcan_link.parse_line(line) is None, line


def test_a_port_whose_set_up_fails_is_closed_again(monkeypatch):
    closed = []

    class Port:
        def write(self, data):
            raise OSError("device disconnected")

        def flush(self):
            pass

        def close(self):
            closed.append(True)

    module = types.ModuleType("serial")
    module.SerialException = OSError
    module.serial_for_url = lambda *args, **kwargs: Port()
    monkeypatch.setitem(sys.modules, "serial", module)
    link = slcan_link.SlcanLink("COM9")
    with pytest.raises(slcan_link.LinkError):
        link.open()
    assert closed == [True]
