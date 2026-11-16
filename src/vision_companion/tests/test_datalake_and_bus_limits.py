# =============================================================================
# URTC-VISION-TOOL - vision_companion tests: test_datalake_and_bus_limits.py
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""Two limits: the write token of the datalake goes only to the address it was given (no redirect is followed,
a plain address to another machine warns or is refused), and one call of the SLCAN receiver ends even on a bus
that is never quiet."""
from __future__ import annotations

import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from vision_companion import export
from vision_companion.slcan_link import SlcanLink

SAMPLE = {"sourceId": "a", "kind": "k", "timestamp": 1, "fields": {}}


def test_the_address_rule_accepts_https_and_this_machine_only() -> None:
    for good in ("https://datalake.example", "http://127.0.0.1:8080", "http://localhost/x", "http://[::1]:80"):
        assert export.plain_datalake_refusal(good) is None, good
    for bad in ("http://datalake.example", "http://192.168.0.20:8080", "https://"):
        assert export.plain_datalake_refusal(bad), bad


def test_a_plain_address_to_another_machine_warns_by_default_and_is_refused_when_the_switch_is_off(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("UVIS_TEST_TOKEN", "secret-value")
    monkeypatch.delenv("UVIS_ALLOW_PLAIN_DATALAKE", raising=False)
    with caplog.at_level("WARNING", logger="vision_companion.export"):
        with pytest.raises(export.ExportError, match="could not be reached"):
            export.post_samples("http://127.0.0.1.invalid:9", [SAMPLE], "UVIS_TEST_TOKEN", timeout_s=1)
    assert any("must not cross a network in clear" in record.message for record in caplog.records)
    monkeypatch.setenv("UVIS_ALLOW_PLAIN_DATALAKE", "0")
    with pytest.raises(export.ExportError, match="UVIS_ALLOW_PLAIN_DATALAKE=0") as caught:
        export.post_samples("http://datalake.example", [SAMPLE], "UVIS_TEST_TOKEN")
    assert "secret-value" not in str(caught.value)


def test_a_redirect_is_not_followed_and_the_token_goes_nowhere_else(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[str, str]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            self.rfile.read(int(self.headers["Content-Length"]))
            seen.append((self.path, self.headers.get("Authorization", "")))
            if self.path == "/ingest":
                self.send_response(302)
                self.send_header("Location", "/elsewhere")
                self.send_header("Content-Length", "0")
            else:
                self.send_response(200)
                self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, *args) -> None:  # noqa: D102
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        monkeypatch.setenv("UVIS_TEST_TOKEN", "abc")
        with pytest.raises(export.ExportError, match="status 302"):
            export.post_samples(f"http://127.0.0.1:{server.server_address[1]}", [SAMPLE], "UVIS_TEST_TOKEN")
    finally:
        server.shutdown()
    assert [path for path, _ in seen] == ["/ingest"]   # /elsewhere was never asked


class NeverQuiet:
    """A serial line on a bus with traffic all the time: every read brings a frame of another node."""

    def __init__(self) -> None:
        self.reads = 0

    def read(self, size: int) -> bytes:
        self.reads += 1
        time.sleep(0.002)
        return b"t1230\r"


def make_link(**options: float) -> SlcanLink:
    link = SlcanLink("COM9", **options)
    link._serial = NeverQuiet()
    return link


def test_a_bus_that_is_never_quiet_does_not_hold_the_receiver_for_ever() -> None:
    link = make_link(total_wait_s=0.1)
    began = time.monotonic()
    messages = link.receive()
    assert time.monotonic() - began < 2.0
    assert messages and all(message.arbitration_id == 0x123 for message in messages)


def test_the_receiver_stops_at_the_most_messages_it_gathers() -> None:
    link = make_link(total_wait_s=30.0, max_messages=5)
    began = time.monotonic()
    assert len(link.receive()) == 5
    assert time.monotonic() - began < 2.0
