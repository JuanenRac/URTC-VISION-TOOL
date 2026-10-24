# =============================================================================
# URTC-VISION-TOOL - tests/test_slcan_link.py
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""The thermal exchange over a serial CAN adapter, with a simulated adapter and head, and the capture command."""
from __future__ import annotations

import json

import numpy as np
import pytest
from slcan_adapter import SimulatedAdapter

from vision_companion import cli, slcan_link
from vision_companion.slcan_link import LinkError, SlcanLink, capture, format_frame, parse_line
from vision_companion.urtc_thermal import (
    CAN_ID_CALIBRATED_REQUEST,
    CAN_ID_STATUS,
    CAN_ID_TRIGGER,
    CanMessage,
    SimulatedThermalHead,
    ThermalProtocolError,
    ThermalStatus,
)


FAST = 0.005  # how long a silence ends an answer: the simulated adapter answers at once


def image(width: int = 32, height: int = 24) -> np.ndarray:
    y, x = np.mgrid[0:height, 0:width]
    return (20.0 + 0.5 * x + 0.25 * y).astype(np.float32)


@pytest.fixture
def adapter():
    made: list[SimulatedAdapter] = []

    def make(head: SimulatedThermalHead | None = None, **options) -> SimulatedAdapter:
        item = SimulatedAdapter(head or SimulatedThermalHead(image()), **options)
        made.append(item)
        return item

    yield make
    for item in made:
        item.close()


def test_a_frame_is_written_and_read_as_slcan_text():
    assert format_frame(CanMessage(0x254, bytes([7]))) == b"t254107\r"
    assert format_frame(CanMessage(0x250)) == b"t2500\r"
    assert parse_line("t25580001020304050607") == CanMessage(0x255, bytes(range(8)))
    assert parse_line("t2500") == CanMessage(0x250)


@pytest.mark.parametrize(
    "line", ["", "\x07", "T000002500", "t25", "tZZZ0", "t2509", "t2502AA", "t2501AABB", "r2500", "O"],
)
def test_what_is_not_a_standard_data_frame_is_not_a_message(line):
    assert parse_line(line) is None


def test_the_image_of_the_head_comes_back_over_the_serial_line(adapter):
    simulated = adapter()
    frame = capture(simulated.url, idle_wait_s=FAST)
    assert frame.shape == (24, 32)
    assert np.allclose(frame, image(), atol=0.006)  # hundredths of a degree
    assert [m.arbitration_id for m in simulated.requests][:2] == [CAN_ID_TRIGGER, CAN_ID_STATUS]
    assert sum(1 for m in simulated.requests if m.arbitration_id == CAN_ID_CALIBRATED_REQUEST) == 48


def test_the_adapter_is_set_up_and_closed_the_way_an_slcan_adapter_wants(adapter):
    simulated = adapter()
    capture(simulated.url, bitrate_kbps=250, idle_wait_s=FAST)
    # the adapter closes the channel before it is set up, sets the bit rate, opens it, and the link closes it again at
    # the end
    assert simulated.commands[:3] == ["C", "S5", "O"]
    assert simulated.commands[-1] == "C"


def test_a_head_that_needs_a_few_polls_is_waited_for(adapter):
    simulated = adapter(SimulatedThermalHead(image(), polls_until_ready=3))
    assert np.allclose(capture(simulated.url, idle_wait_s=FAST), image(), atol=0.006)
    assert sum(1 for m in simulated.requests if m.arbitration_id == CAN_ID_STATUS) == 4


def test_the_small_sensor_has_twelve_chunks(adapter):
    simulated = adapter(SimulatedThermalHead(image(16, 12), variant="90641"))
    assert capture(simulated.url, variant="90641", idle_wait_s=FAST).shape == (12, 16)
    assert sum(1 for m in simulated.requests if m.arbitration_id == CAN_ID_CALIBRATED_REQUEST) == 12


def test_noise_on_the_line_is_ignored(adapter):
    simulated = adapter(garbage_before_answers=True)
    assert np.allclose(capture(simulated.url, idle_wait_s=FAST), image(), atol=0.006)


def test_the_frames_of_a_chunk_that_come_one_by_one_on_a_slow_line_are_put_together(adapter):
    # the pause between two frames is longer than the silence that ends an answer: the next look completes the chunk
    simulated = adapter(SimulatedThermalHead(image(16, 12), variant="90641"), chunk_frame_delay_s=0.03)
    assert np.allclose(capture(simulated.url, variant="90641", idle_wait_s=FAST), image(16, 12), atol=0.006)


def test_a_head_that_reports_an_error_is_an_error(adapter):
    head = SimulatedThermalHead(image())
    head.error_on_trigger = True
    with pytest.raises(ThermalProtocolError, match="capture error"):
        capture(adapter(head).url, idle_wait_s=FAST)
    assert head.status == ThermalStatus.ERROR


def test_a_lost_frame_of_a_chunk_is_reported_with_the_chunk_number(adapter):
    with pytest.raises(ThermalProtocolError, match="chunk 0 was not answered with four frames"):
        capture(adapter(drop_chunk_frames=1).url, idle_wait_s=FAST)


def test_a_head_that_never_answers_ends_the_capture_instead_of_waiting_for_ever(adapter):
    simulated = adapter(silent=True)
    with SlcanLink(simulated.url, first_wait_s=0.05, idle_wait_s=0.02) as link:
        with pytest.raises(ThermalProtocolError, match="did not become ready"):
            slcan_link.read_frame(send=link.send, receive=link.receive, max_polls=3)


def test_a_port_that_cannot_be_opened_is_a_clear_error():
    with pytest.raises(LinkError, match="cannot open"):
        capture("socket://127.0.0.1:1")


def test_a_bit_rate_that_slcan_does_not_have_is_refused():
    with pytest.raises(LinkError, match="not a bit rate of SLCAN"):
        SlcanLink("socket://127.0.0.1:1", bitrate_kbps=333)


def test_sending_on_a_link_that_is_not_open_is_an_error():
    link = SlcanLink("socket://127.0.0.1:1")
    with pytest.raises(LinkError, match="not open"):
        link.send(CanMessage(0x250))
    with pytest.raises(LinkError, match="not open"):
        link.receive()
    link.close()  # closing a link that was never opened is harmless


# ---- the capture command -------------------------------------------------------------------------------------------
# --------------------------


def test_the_capture_command_saves_the_image_where_the_other_commands_read_it(adapter, tmp_path, capsys):
    simulated = adapter()
    code = cli.main(["capture", "--port", simulated.url, "--out", str(tmp_path)])
    assert code == cli.EXIT_OK
    saved = np.load(tmp_path / "thermal_frame.npy")
    assert np.allclose(saved, image(), atol=0.006)
    assert (tmp_path / "thermal_frame_falsecolor.png").is_file()
    assert "thermal frame: 32x24" in capsys.readouterr().out


def test_the_saved_image_can_be_judged_by_the_other_commands(adapter, tmp_path, capsys):
    # a head that sees a warm part: the image crosses the serial line, is saved, and `inspect` judges a region of it
    # from the file
    hot = np.full((24, 32), 24.0, dtype=np.float32)
    hot[0:5, 0:5] = 60.0
    simulated = adapter(SimulatedThermalHead(hot))
    assert cli.main(["capture", "--port", simulated.url, "--out", str(tmp_path)]) == cli.EXIT_OK
    plan = {
        "schema": 1,
        "profile": {
            "name": "after reflow", "ambient_c": 24.0, "rules": {"joint": {"expected_c": 60.0, "tolerance_c": 8.0}},
        },
        "components": [{"ref": "J1", "kind": "joint", "roi": [0, 0, 100, 100], "task": "reflow"}],
    }
    plan_file = tmp_path / "plan.json"
    plan_file.write_text(json.dumps(plan), encoding="utf-8")
    capsys.readouterr()
    assert cli.main(["inspect", str(plan_file), "--frame", str(tmp_path / "thermal_frame.npy")]) == cli.EXIT_OK
    assert "J1" in capsys.readouterr().out


def test_a_head_that_does_not_deliver_is_no_data_and_a_port_that_does_not_open_is_bad_input(adapter, tmp_path, capsys):
    head = SimulatedThermalHead(image())
    head.error_on_trigger = True
    assert cli.main(["capture", "--port", adapter(head).url, "--out", str(tmp_path)]) == cli.EXIT_NO_DATA
    assert "the head did not deliver an image" in capsys.readouterr().err
    assert cli.main(["capture", "--port", "socket://127.0.0.1:1", "--out", str(tmp_path)]) == cli.EXIT_BAD_INPUT
    assert "cannot open" in capsys.readouterr().err


def test_a_degenerate_range_is_refused_before_the_bus_is_touched(tmp_path, capsys):
    arguments = ["capture", "--port", "socket://127.0.0.1:1", "--range", "50", "50", "--out", str(tmp_path)]
    assert cli.main(arguments) == cli.EXIT_BAD_INPUT
    assert "--range needs HIGH greater than LOW" in capsys.readouterr().err
