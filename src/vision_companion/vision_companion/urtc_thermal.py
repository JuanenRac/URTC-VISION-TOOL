# =============================================================================
# URTC-VISION-TOOL - vision_companion thermal messages of URTC: urtc_thermal.py
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""The CAN messages through which a URTC tool head hands over a thermal image.

The vision head is a URTC head: its thermal data travels in the messages of the URTC thermal
inspection tool (tool profile 22, identifiers ``0x250``-``0x255``, documented in URTC's
``docs/CANBUS.TXT``), not in a protocol of its own. This module is the host side of that
conversation and nothing else: it builds the request messages, reads the answers and puts the
chunks of the calibrated image back together. It has no bus access (hand the messages to
python-can, SLCAN or whatever carries the bus), so it runs and is tested without hardware, and
:class:`SimulatedThermalHead` answers like a head so the whole exchange can be played back.

The exchange, as URTC defines it:

* ``0x250`` starts a capture (the payload is ignored);
* ``0x251`` asks for the status; the head answers one byte: 0 idle, 1 busy, 2 ready, 0xFF error;
* ``0x254`` with one byte (the chunk index) asks for 16 calibrated pixels; the head answers with
  exactly four ``0x255`` frames of eight bytes, in order, 16 big-endian ``int16`` values in
  hundredths of a degree Celsius. Fewer than four frames is an incomplete answer;
* ``0x252``/``0x253`` are the same exchange for the raw sensor words (not used here).

A 32x24 sensor (MLX90640, MLX90642) has 48 chunks, a 16x12 one (MLX90641) has 12; the pixels
are in row-major order.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import IntEnum

import numpy as np

TOOL_ID_THERMAL_INSPECTION = 22

CAN_ID_TRIGGER = 0x250
CAN_ID_STATUS = 0x251
CAN_ID_RAW_REQUEST = 0x252
CAN_ID_RAW_CHUNK = 0x253
CAN_ID_CALIBRATED_REQUEST = 0x254
CAN_ID_CALIBRATED_CHUNK = 0x255

PIXELS_PER_CHUNK = 16
FRAMES_PER_CHUNK = 4
BYTES_PER_FRAME = 8
CENTI_DEGREES = 100.0

#: sensor variant -> (width, height); the chunk count follows from it.
VARIANT_SHAPES: dict[str, tuple[int, int]] = {
    "90640": (32, 24),
    "90641": (16, 12),
    "90642": (32, 24),
}


class ThermalStatus(IntEnum):
    IDLE = 0x00
    BUSY = 0x01
    READY = 0x02
    ERROR = 0xFF


class ThermalProtocolError(ValueError):
    """A message that is not what the thermal inspection tool sends."""


@dataclass(frozen=True)
class CanMessage:
    """A classic CAN data frame: an 11-bit identifier and up to eight data bytes."""

    arbitration_id: int
    data: bytes = b""

    def __post_init__(self) -> None:
        if not 0 <= self.arbitration_id <= 0x7FF:
            raise ThermalProtocolError(f"identifier {self.arbitration_id:#x} is not an 11-bit identifier")
        if len(self.data) > BYTES_PER_FRAME:
            raise ThermalProtocolError("a CAN data frame carries at most 8 bytes")


def chunk_count(variant: str) -> int:
    width, height = _shape(variant)
    return width * height // PIXELS_PER_CHUNK


def _shape(variant: str) -> tuple[int, int]:
    try:
        return VARIANT_SHAPES[variant]
    except KeyError:
        known = ", ".join(VARIANT_SHAPES)
        raise ThermalProtocolError(f"unknown sensor variant {variant!r} (expected one of {known})") from None


def trigger_message() -> CanMessage:
    """Starts a new capture."""
    return CanMessage(CAN_ID_TRIGGER)


def status_request() -> CanMessage:
    return CanMessage(CAN_ID_STATUS)


def calibrated_chunk_request(index: int) -> CanMessage:
    if not 0 <= index <= 0xFF:
        raise ThermalProtocolError(f"chunk index {index} does not fit in one byte")
    return CanMessage(CAN_ID_CALIBRATED_REQUEST, bytes([index]))


def parse_status(message: CanMessage) -> ThermalStatus:
    """The status carried by an answer on ``0x251``."""
    if message.arbitration_id != CAN_ID_STATUS or len(message.data) != 1:
        raise ThermalProtocolError("a status answer is one byte on 0x251")
    try:
        return ThermalStatus(message.data[0])
    except ValueError:
        raise ThermalProtocolError(f"unknown capture status {message.data[0]:#04x}") from None


class FrameAssembler:
    """Collects the calibrated chunks of one image and gives back the temperatures in degrees C.

    Typical use: send :func:`trigger_message`, wait for :class:`ThermalStatus` ``READY``, then loop
    ``while not assembler.complete: send(assembler.next_request()); for each frame received:
    assembler.feed(frame)``. A chunk whose four frames did not all arrive is not stored; ask for it
    again with :meth:`next_request` after :meth:`abandon_chunk`.
    """

    def __init__(self, variant: str = "90640") -> None:
        self.variant = variant
        self.width, self.height = _shape(variant)
        self.chunks = chunk_count(variant)
        self._values = np.zeros(self.width * self.height, dtype=np.int16)
        self._have = [False] * self.chunks
        self._pending = bytearray()
        self._asked: int | None = None

    @property
    def complete(self) -> bool:
        return all(self._have)

    @property
    def missing(self) -> list[int]:
        return [index for index, have in enumerate(self._have) if not have]

    def next_request(self) -> CanMessage:
        """The request for the first chunk still missing (and the chunk the next frames are taken to answer)."""
        missing = self.missing
        if not missing:
            raise ThermalProtocolError("the image is complete: there is nothing left to ask for")
        self._asked = missing[0]
        self._pending = bytearray()
        return calibrated_chunk_request(self._asked)

    def abandon_chunk(self) -> None:
        """Forgets the frames received so far for the chunk being asked for (a timeout, a lost frame)."""
        self._pending = bytearray()
        self._asked = None

    def feed(self, message: CanMessage) -> bool:
        """Takes one received message. Returns True when it completed a chunk.

        Messages of other identifiers are ignored. A frame of ``0x255`` that is not eight bytes, or that
        arrives when no chunk was asked for, is an error: the exchange is out of step.
        """
        if message.arbitration_id != CAN_ID_CALIBRATED_CHUNK:
            return False
        if self._asked is None:
            raise ThermalProtocolError("a calibrated chunk frame arrived but no chunk was asked for")
        if len(message.data) != BYTES_PER_FRAME:
            self.abandon_chunk()
            raise ThermalProtocolError("a calibrated chunk frame is eight bytes")
        self._pending += message.data
        if len(self._pending) < FRAMES_PER_CHUNK * BYTES_PER_FRAME:
            return False
        index = self._asked
        words = np.frombuffer(bytes(self._pending), dtype=">i2")
        start = index * PIXELS_PER_CHUNK
        self._values[start:start + PIXELS_PER_CHUNK] = words
        self._have[index] = True
        self._asked = None
        self._pending = bytearray()
        return True

    def frame_c(self) -> np.ndarray:
        """The image in degrees Celsius, shape (height, width), as float32. Only when complete."""
        if not self.complete:
            raise ThermalProtocolError(f"{len(self.missing)} chunk(s) are still missing")
        return (self._values.astype(np.float32) / np.float32(CENTI_DEGREES)).reshape(self.height, self.width)


class SimulatedThermalHead:
    """Answers like a URTC head with the thermal inspection tool, from a given image in degrees C.

    It follows the documented behaviour: no answer to a chunk request unless a capture is ready, the
    status goes busy then ready, values are clamped to the int16 range of hundredths of a degree.
    ``polls_until_ready`` is how many status queries answer *busy* after a trigger.
    """

    def __init__(self, frame_c: np.ndarray, variant: str = "90640", polls_until_ready: int = 0) -> None:
        width, height = _shape(variant)
        if frame_c.shape != (height, width):
            raise ThermalProtocolError(f"a {variant} image is {width}x{height} pixels, got shape {frame_c.shape}")
        self.variant = variant
        centi = np.rint(frame_c.astype(np.float64) * CENTI_DEGREES)
        self._centi = np.clip(centi, -32768, 32767).astype(">i2").reshape(-1)
        self.polls_until_ready = polls_until_ready
        self.status = ThermalStatus.IDLE
        self._busy_polls_left = 0
        self.error_on_trigger = False

    def handle(self, message: CanMessage) -> list[CanMessage]:
        """The messages the head sends in answer to ``message`` (possibly none)."""
        if message.arbitration_id == CAN_ID_TRIGGER:
            if self.error_on_trigger:
                self.status = ThermalStatus.ERROR
            else:
                self.status = ThermalStatus.BUSY
                self._busy_polls_left = self.polls_until_ready
            return []
        if message.arbitration_id == CAN_ID_STATUS:
            if self.status == ThermalStatus.BUSY:
                if self._busy_polls_left > 0:
                    self._busy_polls_left -= 1
                else:
                    self.status = ThermalStatus.READY
            return [CanMessage(CAN_ID_STATUS, bytes([self.status]))]
        if message.arbitration_id == CAN_ID_CALIBRATED_REQUEST:
            if self.status != ThermalStatus.READY or len(message.data) < 1:
                return []
            index = message.data[0]
            if index >= chunk_count(self.variant):
                return []
            payload = self._centi[index * PIXELS_PER_CHUNK:(index + 1) * PIXELS_PER_CHUNK].tobytes()
            return [
                CanMessage(CAN_ID_CALIBRATED_CHUNK, payload[i:i + BYTES_PER_FRAME])
                for i in range(0, len(payload), BYTES_PER_FRAME)
            ]
        return []


def read_frame(
    *,
    send: Callable[[CanMessage], None],
    receive: Callable[[], list[CanMessage]],
    variant: str = "90640",
    max_polls: int = 50,
) -> np.ndarray:
    """Runs a whole capture over two callables: ``send(message)`` and ``receive() -> list[CanMessage]``.

    ``receive`` returns the messages that arrived since the last call (an empty list for none). Raises
    :class:`ThermalProtocolError` when the head reports an error, never becomes ready, or does not answer a
    chunk request with its four frames.
    """
    send(trigger_message())
    for _ in range(max_polls):
        send(status_request())
        answers = [m for m in receive() if m.arbitration_id == CAN_ID_STATUS]
        if not answers:
            continue
        status = parse_status(answers[-1])
        if status == ThermalStatus.ERROR:
            raise ThermalProtocolError("the head reports a capture error")
        if status == ThermalStatus.READY:
            break
    else:
        raise ThermalProtocolError("the head did not become ready")
    assembler = FrameAssembler(variant)
    while not assembler.complete:
        send(assembler.next_request())
        done = False
        for frame in (m for m in receive() if m.arbitration_id == CAN_ID_CALIBRATED_CHUNK):
            done = assembler.feed(frame) or done
        if not done:
            index = assembler.missing[0]
            assembler.abandon_chunk()
            raise ThermalProtocolError(f"chunk {index} was not answered with four frames")
    return assembler.frame_c()
