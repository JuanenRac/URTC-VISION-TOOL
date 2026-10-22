from __future__ import annotations

import numpy as np
import pytest

from vision_companion import cli, urtc_thermal as ut


def _frame(variant: str = "90640") -> np.ndarray:
    width, height = ut.VARIANT_SHAPES[variant]
    return cli.generate_synthetic_thermal_frame(width, height)


def test_the_identifiers_are_the_ones_of_the_thermal_inspection_tool() -> None:
    assert ut.TOOL_ID_THERMAL_INSPECTION == 22
    assert [ut.CAN_ID_TRIGGER, ut.CAN_ID_STATUS, ut.CAN_ID_RAW_REQUEST, ut.CAN_ID_RAW_CHUNK,
            ut.CAN_ID_CALIBRATED_REQUEST, ut.CAN_ID_CALIBRATED_CHUNK] == [0x250, 0x251, 0x252, 0x253, 0x254, 0x255]


def test_chunk_counts_follow_the_sensor_variant() -> None:
    assert ut.chunk_count("90640") == 48
    assert ut.chunk_count("90642") == 48
    assert ut.chunk_count("90641") == 12
    with pytest.raises(ut.ThermalProtocolError):
        ut.chunk_count("90643")


def test_request_messages() -> None:
    assert ut.trigger_message() == ut.CanMessage(0x250, b"")
    assert ut.status_request() == ut.CanMessage(0x251, b"")
    assert ut.calibrated_chunk_request(7) == ut.CanMessage(0x254, b"\x07")
    with pytest.raises(ut.ThermalProtocolError):
        ut.calibrated_chunk_request(256)
    with pytest.raises(ut.ThermalProtocolError):
        ut.CanMessage(0x800)
    with pytest.raises(ut.ThermalProtocolError):
        ut.CanMessage(0x255, bytes(9))


def test_status_answers() -> None:
    codes = (
        (0, ut.ThermalStatus.IDLE), (1, ut.ThermalStatus.BUSY),
        (2, ut.ThermalStatus.READY), (0xFF, ut.ThermalStatus.ERROR),
    )
    for code, status in codes:
        assert ut.parse_status(ut.CanMessage(0x251, bytes([code]))) is status
    wrong = (
        ut.CanMessage(0x251, b"\x07"), ut.CanMessage(0x251, b""),
        ut.CanMessage(0x251, b"\x02\x00"), ut.CanMessage(0x252, b"\x02"),
    )
    for bad in wrong:
        with pytest.raises(ut.ThermalProtocolError):
            ut.parse_status(bad)


@pytest.mark.parametrize("variant", ["90640", "90641", "90642"])
def test_a_whole_image_travels_through_the_exchange_with_hundredth_degree_precision(variant: str) -> None:
    truth = _frame(variant)
    head = ut.SimulatedThermalHead(truth, variant, polls_until_ready=3)
    inbox: list[ut.CanMessage] = []
    sent: list[ut.CanMessage] = []

    def send(message: ut.CanMessage) -> None:
        sent.append(message)
        inbox.extend(head.handle(message))

    def receive() -> list[ut.CanMessage]:
        taken = list(inbox)
        inbox.clear()
        return taken

    got = ut.read_frame(send=send, receive=receive, variant=variant)
    assert got.shape == truth.shape and got.dtype == np.float32
    assert np.allclose(got, truth, atol=0.005 + 1e-3)
    chunk_requests = [m for m in sent if m.arbitration_id == 0x254]
    assert [m.data[0] for m in chunk_requests] == list(range(ut.chunk_count(variant)))
    assert sent[0] == ut.trigger_message()


def test_the_pixels_are_row_major_and_big_endian() -> None:
    truth = np.zeros((24, 32), dtype=np.float32)
    truth[0, 1] = 25.50   # second pixel of chunk 0
    truth[1, 0] = -3.25   # pixel 32: first pixel of chunk 2
    head = ut.SimulatedThermalHead(truth)
    head.handle(ut.trigger_message())
    head.handle(ut.status_request())
    first = head.handle(ut.calibrated_chunk_request(0))
    assert len(first) == 4 and all(m.arbitration_id == 0x255 and len(m.data) == 8 for m in first)
    assert first[0].data[2:4] == (2550).to_bytes(2, "big")
    third = head.handle(ut.calibrated_chunk_request(2))
    assert third[0].data[0:2] == (-325).to_bytes(2, "big", signed=True)


def test_values_beyond_the_int16_range_are_clamped_like_the_firmware_does() -> None:
    truth = np.full((12, 16), 25.0, dtype=np.float32)
    truth[0, 0] = 500.0
    truth[0, 1] = -500.0
    head = ut.SimulatedThermalHead(truth, "90641")
    head.handle(ut.trigger_message())
    head.handle(ut.status_request())
    asm = ut.FrameAssembler("90641")
    for _ in range(12):
        for frame in head.handle(asm.next_request()):
            asm.feed(frame)
    image = asm.frame_c()
    assert image[0, 0] == pytest.approx(327.67, abs=0.01) and image[0, 1] == pytest.approx(-327.68, abs=0.01)


def test_the_head_does_not_answer_a_chunk_request_before_the_capture_is_ready() -> None:
    head = ut.SimulatedThermalHead(_frame(), polls_until_ready=2)
    assert head.handle(ut.calibrated_chunk_request(0)) == []
    head.handle(ut.trigger_message())
    assert head.handle(ut.calibrated_chunk_request(0)) == []
    assert ut.parse_status(head.handle(ut.status_request())[0]) is ut.ThermalStatus.BUSY
    assert ut.parse_status(head.handle(ut.status_request())[0]) is ut.ThermalStatus.BUSY
    assert ut.parse_status(head.handle(ut.status_request())[0]) is ut.ThermalStatus.READY
    assert len(head.handle(ut.calibrated_chunk_request(0))) == 4
    assert head.handle(ut.calibrated_chunk_request(48)) == []


def test_a_short_answer_is_an_incomplete_chunk_not_a_wrong_image() -> None:
    head = ut.SimulatedThermalHead(_frame())
    head.handle(ut.trigger_message())
    head.handle(ut.status_request())
    asm = ut.FrameAssembler()
    frames = head.handle(asm.next_request())
    assert [asm.feed(f) for f in frames[:3]] == [False, False, False]
    assert asm.missing[0] == 0 and not asm.complete
    asm.abandon_chunk()
    frames = head.handle(asm.next_request())
    assert [asm.feed(f) for f in frames] == [False, False, False, True]
    assert asm.missing[0] == 1
    with pytest.raises(ut.ThermalProtocolError):
        asm.frame_c()


def test_frames_out_of_step_are_errors_and_other_traffic_is_ignored() -> None:
    asm = ut.FrameAssembler()
    assert asm.feed(ut.CanMessage(0x100, b"\x00" * 8)) is False
    with pytest.raises(ut.ThermalProtocolError):
        asm.feed(ut.CanMessage(0x255, b"\x00" * 8))
    asm.next_request()
    with pytest.raises(ut.ThermalProtocolError):
        asm.feed(ut.CanMessage(0x255, b"\x00" * 7))


def test_nothing_is_left_to_ask_for_when_the_image_is_complete() -> None:
    truth = _frame("90641")
    head = ut.SimulatedThermalHead(truth, "90641")
    head.handle(ut.trigger_message())
    head.handle(ut.status_request())
    asm = ut.FrameAssembler("90641")
    while not asm.complete:
        for frame in head.handle(asm.next_request()):
            asm.feed(frame)
    with pytest.raises(ut.ThermalProtocolError):
        asm.next_request()


def test_read_frame_reports_an_error_status_a_head_that_never_gets_ready_and_a_silent_chunk() -> None:
    truth = _frame()

    def run(head: ut.SimulatedThermalHead, **kw: object) -> np.ndarray:
        inbox: list[ut.CanMessage] = []

        def send(message: ut.CanMessage) -> None:
            inbox.extend(head.handle(message))

        def receive() -> list[ut.CanMessage]:
            taken = list(inbox)
            inbox.clear()
            return taken

        return ut.read_frame(send=send, receive=receive, **kw)  # type: ignore[arg-type]

    broken = ut.SimulatedThermalHead(truth)
    broken.error_on_trigger = True
    with pytest.raises(ut.ThermalProtocolError, match="capture error"):
        run(broken)
    with pytest.raises(ut.ThermalProtocolError, match="did not become ready"):
        run(ut.SimulatedThermalHead(truth, polls_until_ready=100), max_polls=5)

    class Dropping(ut.SimulatedThermalHead):
        def handle(self, message: ut.CanMessage) -> list[ut.CanMessage]:
            answer = super().handle(message)
            return answer[:3] if message.arbitration_id == 0x254 else answer

    with pytest.raises(ut.ThermalProtocolError, match="four frames"):
        run(Dropping(truth))


def test_the_simulator_refuses_an_image_of_the_wrong_shape() -> None:
    with pytest.raises(ut.ThermalProtocolError):
        ut.SimulatedThermalHead(np.zeros((12, 16), dtype=np.float32), "90640")
