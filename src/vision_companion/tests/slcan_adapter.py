# =============================================================================
# URTC-VISION-TOOL - tests/slcan_adapter.py
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""A simulated serial CAN adapter with a simulated thermal head behind it, listening on a local TCP port.

pyserial opens ``socket://127.0.0.1:PORT`` like a serial port, so the code under test is the real code, bytes and all:
the
commands of the adapter (``C``, ``S6``, ``O``), the frames as SLCAN text, the carriage returns. What answers is
``SimulatedThermalHead``, a model written from the same description of the protocol, so a test shows that the two
agree, not that
a real head behaves this way.
"""
from __future__ import annotations

import socket
import threading
import time

from vision_companion.slcan_link import format_frame, parse_line
from vision_companion.urtc_thermal import CAN_ID_CALIBRATED_CHUNK, CanMessage, SimulatedThermalHead


class SimulatedAdapter:
    def __init__(self, head: SimulatedThermalHead, *, drop_chunk_frames: int = 0, garbage_before_answers: bool = False,
                 silent: bool = False, chunk_frame_delay_s: float = 0.0) -> None:
        self.head = head
        # a slow line: the frames of an answer come one by one, this far apart
        self.chunk_frame_delay_s = chunk_frame_delay_s
        self.drop_chunk_frames = drop_chunk_frames  # how many frames of chunk answers to lose (a line that drops one)
        self.garbage_before_answers = garbage_before_answers
        self.silent = silent
        self.commands: list[str] = []
        self.requests: list[CanMessage] = []
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.bind(("127.0.0.1", 0))
        self._server.listen(1)
        self._server.settimeout(10)
        self._thread = threading.Thread(target=self._serve, name="simulated-slcan-adapter", daemon=True)
        self._thread.start()

    @property
    def url(self) -> str:
        return f"socket://127.0.0.1:{self._server.getsockname()[1]}"

    def _serve(self) -> None:
        try:
            connection, _address = self._server.accept()
        except OSError:
            return
        connection.settimeout(0.2)
        buffer = b""
        with connection:
            while True:
                try:
                    chunk = connection.recv(256)
                except TimeoutError:
                    continue
                except OSError:
                    return
                if not chunk:
                    return
                buffer += chunk
                *lines, buffer = buffer.split(b"\r")
                for raw in lines:
                    self._handle(connection, raw.decode("ascii", errors="replace"))

    def _handle(self, connection: socket.socket, line: str) -> None:
        if not line:
            return
        if not line.startswith("t"):
            self.commands.append(line)
            connection.sendall(b"\r")  # an SLCAN adapter acknowledges a command with a carriage return
            return
        message = parse_line(line)
        if message is None or self.silent:
            return
        self.requests.append(message)
        pieces: list[bytes] = []
        if self.garbage_before_answers:
            # an error bell, an extended frame, junk and a frame of another node
            pieces.append(b"\x07\rT0000000100\rtZZZ\rt1230\r")
        for answer in self.head.handle(message):
            if answer.arbitration_id == CAN_ID_CALIBRATED_CHUNK and self.drop_chunk_frames > 0:
                self.drop_chunk_frames -= 1
                continue
            pieces.append(format_frame(answer))
        if self.chunk_frame_delay_s:
            for piece in pieces:
                connection.sendall(piece)
                time.sleep(self.chunk_frame_delay_s)
        elif pieces:
            connection.sendall(b"".join(pieces))  # one write: the answer reaches the line as one burst

    def close(self) -> None:
        try:
            self._server.close()
        except OSError:
            pass
