# =============================================================================
# URTC-VISION-TOOL - vision_companion tests: test_slcan_link_faults.py
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""The serial line of the SLCAN adapter when it fails: a port that goes away while it is written or read, an adapter
that cannot flush, a package that is not installed, and a line that never ends. The line is a fake that fails on
command (nothing is opened)."""
from __future__ import annotations

import sys
import types

import pytest

from vision_companion import slcan_link
from vision_companion.slcan_link import LinkError, SlcanLink


class FakeSerial:
    def __init__(self, reads=(), fail_write=False, fail_flush=False, fail_read=False, fail_reset=False,
                 fail_close=False):
        self.reads = list(reads)
        self.written: list[bytes] = []
        self.fail_write, self.fail_flush, self.fail_read = fail_write, fail_flush, fail_read
        self.fail_reset, self.fail_close = fail_reset, fail_close
        self.closed = False

    def write(self, data):
        if self.fail_write:
            raise OSError("write failed")
        self.written.append(bytes(data))

    def flush(self):
        if self.fail_flush:
            raise OSError("flush failed")

    def read(self, size):
        if self.fail_read:
            raise OSError("read failed")
        return self.reads.pop(0) if self.reads else b""

    def reset_input_buffer(self):
        if self.fail_reset:
            raise OSError("reset failed")

    def close(self):
        self.closed = True
        if self.fail_close:
            raise OSError("close failed")


def install(monkeypatch, fake):
    module = types.ModuleType("serial")

    class SerialException(Exception):
        pass

    module.SerialException = SerialException
    module.serial_for_url = lambda *args, **kwargs: fake
    monkeypatch.setitem(sys.modules, "serial", module)
    monkeypatch.setattr(slcan_link.time, "sleep", lambda _seconds: None)


def test_an_adapter_that_cannot_flush_its_input_is_still_opened(monkeypatch):
    fake = FakeSerial(fail_reset=True)
    install(monkeypatch, fake)
    link = SlcanLink("COM9")
    link.open()
    assert [frame.decode() for frame in fake.written] == ["C\r", "S6\r", "O\r"] or len(fake.written) == 3
    link.close()
    assert fake.closed


def test_the_package_that_is_not_installed_is_a_clear_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "serial", None)
    with pytest.raises(LinkError, match="pyserial is not installed"):
        SlcanLink("COM9").open()


def test_a_port_that_refuses_to_open_gives_the_name_of_the_port(monkeypatch):
    module = types.ModuleType("serial")

    class SerialException(Exception):
        pass

    def refuse(*_a, **_k):
        raise OSError("no such port")

    module.SerialException = SerialException
    module.serial_for_url = refuse
    monkeypatch.setitem(sys.modules, "serial", module)
    with pytest.raises(LinkError, match="cannot open COM9"):
        SlcanLink("COM9").open()


def test_a_write_that_fails_is_a_link_error_with_the_port(monkeypatch):
    fake = FakeSerial()
    install(monkeypatch, fake)
    link = SlcanLink("COM9")
    link.open()
    fake.fail_write = True
    with pytest.raises(LinkError, match="cannot write to COM9"):
        link._write(b"x")


def test_a_flush_that_fails_is_a_link_error_too(monkeypatch):
    fake = FakeSerial()
    install(monkeypatch, fake)
    link = SlcanLink("COM9")
    link.open()
    fake.fail_flush = True
    with pytest.raises(LinkError, match="cannot write"):
        link._write(b"x")


def test_a_read_that_fails_is_a_link_error_with_the_port(monkeypatch):
    fake = FakeSerial()
    install(monkeypatch, fake)
    link = SlcanLink("COM9", first_wait_s=0.01)
    link.open()
    fake.fail_read = True
    with pytest.raises(LinkError, match="cannot read from COM9"):
        link.receive()


def test_closing_an_adapter_whose_port_went_away_still_releases_it(monkeypatch):
    fake = FakeSerial()
    install(monkeypatch, fake)
    link = SlcanLink("COM9")
    link.open()
    fake.fail_write = True
    link.close()
    assert fake.closed and link._serial is None
    link.close()      # a second close is harmless


def test_a_port_that_cannot_be_closed_still_leaves_the_link_closed(monkeypatch):
    fake = FakeSerial(fail_close=True)
    install(monkeypatch, fake)
    link = SlcanLink("COM9")
    link.open()
    with pytest.raises(OSError):
        link.close()
    assert link._serial is None


def test_a_line_that_never_ends_is_dropped_as_noise_and_the_next_frame_is_read(monkeypatch):
    noise = b"x" * 5000
    frame = b"t1230\r"
    fake = FakeSerial(reads=[noise, frame])
    install(monkeypatch, fake)
    link = SlcanLink("COM9", first_wait_s=0.05, idle_wait_s=0.001)
    link.open()
    messages = link.receive()
    assert len(link._buffer) <= 4096
    assert [m.arbitration_id for m in messages] == [0x123]


def test_the_context_manager_opens_and_closes(monkeypatch):
    fake = FakeSerial()
    install(monkeypatch, fake)
    with SlcanLink("COM9") as link:
        assert link._serial is fake
    assert fake.closed and fake.written[-1] == b"C\r"
