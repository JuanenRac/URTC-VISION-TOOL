# =============================================================================
# URTC-VISION-TOOL - vision_companion thermal capture over a serial CAN adapter: slcan_link.py
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""A serial CAN adapter (SLCAN, as the CANable and similar ones speak it) carrying the thermal exchange of urtc_thermal.

``urtc_thermal`` knows the messages and has no bus; this module is the bus. It speaks the small part of SLCAN the
exchange needs:
``C`` closes the channel, ``S6`` sets 500 kbit/s (the bit rate of a URTC bus), ``O`` opens it, and a standard data
frame is
``t`` + three hex digits of identifier + one digit of length + the data in hex + a carriage return. Anything else the
adapter says
(the carriage return that acknowledges a command, a frame of another kind) is ignored.

The port is whatever pyserial can open: ``COM3``, ``/dev/ttyACM0`` or a URL such as ``socket://127.0.0.1:7777`` (a
simulated adapter
in a test). pyserial is imported when the port is opened, so the rest of the package works without it.

Nothing here has been run against a real adapter or a real head; the tests play a simulated head through a simulated
adapter.
"""
from __future__ import annotations

import re
import time
from types import TracebackType

import numpy as np

from .urtc_thermal import CanMessage, ThermalProtocolError, read_frame

# the bit rate codes of SLCAN; a URTC bus runs at 500 kbit/s
BITRATE_CODES = {10: "0", 20: "1", 50: "2", 100: "3", 125: "4", 250: "5", 500: "6", 800: "7", 1000: "8"}
DEFAULT_BITRATE_KBPS = 500
_FRAME = re.compile(r"^t([0-9A-Fa-f]{3})([0-8])([0-9A-Fa-f]*)$")


class LinkError(RuntimeError):
    """The adapter could not be opened or used."""


def format_frame(message: CanMessage) -> bytes:
    """The SLCAN text of a standard data frame, with its carriage return."""
    return f"t{message.arbitration_id:03X}{len(message.data)}{message.data.hex().upper()}\r".encode("ascii")


def parse_line(line: str) -> CanMessage | None:
    """The message of one SLCAN line, or None when the line is anything but a well-formed standard data frame."""
    match = _FRAME.match(line.strip())
    if match is None:
        return None
    data = match.group(3)
    if len(data) != 2 * int(match.group(2)):
        return None
    return CanMessage(int(match.group(1), 16), bytes.fromhex(data))


class SlcanLink:
    """An SLCAN adapter opened on a serial port: ``send`` a message, ``receive`` what arrives."""

    def __init__(self, port: str, *, bitrate_kbps: int = DEFAULT_BITRATE_KBPS, baudrate: int = 115200,
                 first_wait_s: float = 0.5, idle_wait_s: float = 0.03) -> None:
        if bitrate_kbps not in BITRATE_CODES:
            known = ", ".join(str(k) for k in BITRATE_CODES)
            raise LinkError(f"{bitrate_kbps} kbit/s is not a bit rate of SLCAN (one of {known})")
        self.port = port
        self.bitrate_kbps = bitrate_kbps
        self.baudrate = baudrate
        self.first_wait_s = first_wait_s  # how long receive() waits for the first byte of an answer
        self.idle_wait_s = idle_wait_s    # and how long a silence after data ends the answer
        self._serial = None
        self._buffer = ""

    def open(self) -> None:
        try:
            import serial
        except ImportError as error:
            raise LinkError("pyserial is not installed (python -m pip install pyserial)") from error
        try:
            self._serial = serial.serial_for_url(self.port, baudrate=self.baudrate, timeout=0.01)
        except (OSError, ValueError, serial.SerialException) as error:
            raise LinkError(f"cannot open {self.port}: {error}") from error
        self._buffer = ""
        for command in ("C", f"S{BITRATE_CODES[self.bitrate_kbps]}", "O"):
            self._write((command + "\r").encode("ascii"))
            time.sleep(0.02)
        self._discard()

    def close(self) -> None:
        if self._serial is None:
            return
        try:
            self._write(b"C\r")
        except LinkError:
            pass
        finally:
            try:
                self._serial.close()
            finally:
                self._serial = None

    def __enter__(self) -> SlcanLink:
        self.open()
        return self

    def __exit__(
        self, kind: type[BaseException] | None, value: BaseException | None, trace: TracebackType | None,
    ) -> None:
        self.close()

    def _write(self, data: bytes) -> None:
        if self._serial is None:
            raise LinkError("the adapter is not open")
        try:
            self._serial.write(data)
            self._serial.flush()
        except OSError as error:
            raise LinkError(f"cannot write to {self.port}: {error}") from error

    def _discard(self) -> None:
        """What the adapter said while it was being set up (acknowledgements, frames of other nodes) answers nothing."""
        assert self._serial is not None
        try:
            self._serial.reset_input_buffer()
        except OSError:
            pass
        self._buffer = ""

    def send(self, message: CanMessage) -> None:
        self._write(format_frame(message))

    def receive(self) -> list[CanMessage]:
        """The messages that arrive after the last call: waits for the first byte, then until the line is quiet."""
        if self._serial is None:
            raise LinkError("the adapter is not open")
        messages: list[CanMessage] = []
        deadline = time.monotonic() + self.first_wait_s
        quiet_since: float | None = None
        while True:
            try:
                chunk = self._serial.read(256)
            except OSError as error:
                raise LinkError(f"cannot read from {self.port}: {error}") from error
            now = time.monotonic()
            if chunk:
                self._buffer += chunk.decode("ascii", errors="replace")
                quiet_since = now
                *lines, self._buffer = self._buffer.split("\r")
                for line in lines:
                    message = parse_line(line)
                    if message is not None:
                        messages.append(message)
            elif quiet_since is not None and now - quiet_since >= self.idle_wait_s:
                return messages
            elif quiet_since is None and now >= deadline:
                return messages
            if len(self._buffer) > 4096:  # a line that never ends is noise, not a frame
                self._buffer = ""


def capture(port: str, *, variant: str = "90640", bitrate_kbps: int = DEFAULT_BITRATE_KBPS, max_polls: int = 50,
            idle_wait_s: float = 0.03) -> np.ndarray:
    """One calibrated image from the thermal head on the bus behind ``port``, in degrees Celsius, (height, width).

    Raises :class:`LinkError` when the adapter cannot be used and :class:`ThermalProtocolError` when the head does not
    carry out the exchange.
    """
    with SlcanLink(port, bitrate_kbps=bitrate_kbps, idle_wait_s=idle_wait_s) as link:
        return read_frame(send=link.send, receive=link.receive, variant=variant, max_polls=max_polls)


__all__ = ["BITRATE_CODES", "LinkError", "SlcanLink", "ThermalProtocolError", "capture", "format_frame", "parse_line"]
