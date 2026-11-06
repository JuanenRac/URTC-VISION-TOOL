#!/usr/bin/env python3
# =============================================================================
# URTC-VISION-TOOL - tools/sensor_bench.py
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""The software bench of the thermal sensor link: scenarios with faults played through the real receive path, with no sensor and no board.

The receive path of the vision head (receive ring, frame assembly with resynchronisation, frame layer, reading validation, freshness, rate limiter, diagnostics and
silence watch) is compiled for the host and put behind a text port (tests/virtual_sensor.c). This tool builds it, plays scenarios through it - good readings, damaged
and cut frames, noise, repeats, frozen data, readings out of range, another sensor, a sensor that goes silent and comes back, a burst that overflows the ring, and seeded
random runs with injected faults - and checks every answer two ways:

* against what each scenario must produce (written by hand from the rules of the link, never taken from a run);
* against a reference written in this file from those rules: the same frames go through it and the accepted readings and the counters of the link must be identical
  after every step.

    python tools/sensor_bench.py                   # build and run every scenario (CI sets the lock aside; elsewhere ALLOW_LOCAL_BUILD=1)
    python tools/sensor_bench.py --list            # the scenarios
    python tools/sensor_bench.py --only NAME       # one scenario (repeatable)
    python tools/sensor_bench.py --seed 7 --events 3000
    python tools/sensor_bench.py --dump DIR        # write the script of every scenario (replay with --replay)
    python tools/sensor_bench.py --replay FILE     # play a recorded script through the virtual sensor link and print what it answered

This is a sensor link with no sensor: the run says nothing about the camera, the bus driver or the electrical side. Exit status: 0 passed, 1 a check failed, 2 skipped
because no host compiler was found or local builds are locked.
"""
from __future__ import annotations

import argparse
import os
import random
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Mapping

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from local_build import local_build_refusal  # noqa: E402  (the lock on builds that compile on this PC: copied by vendor_copy.py)
except ImportError:   # a repository that has not taken the helper yet keeps the same rule
    def local_build_refusal(env: Mapping[str, str] | None = None) -> str | None:
        env = os.environ if env is None else env
        if env.get("ALLOW_LOCAL_BUILD", "").strip() == "1" or any(env.get(n, "").strip().lower() not in ("", "0", "false", "no", "off") for n in ("CI", "GITHUB_ACTIONS")):
            return None
        return "local C builds are off; GitHub Actions builds it. Set ALLOW_LOCAL_BUILD=1 to allow it on this PC"

SOURCES = ["tests/virtual_sensor.c", "src/rate_limiter.c", "src/sensor_diagnostics.c", "src/sensor_frame.c", "src/sensor_freshness.c", "src/sensor_reading.c", "src/sensor_rx.c",
           "src/vision_sensor_link.c"]
INCLUDES = ["src", "tests"]
FLAGS = ["-std=c11", "-Wall", "-Wextra", "-Wconversion", "-O1", "-g"]
SANITIZE = ["-fsanitize=address,undefined", "-fno-sanitize-recover=undefined"]

# The link (the same numbers as src/sensor_frame.h, src/sensor_reading.h and tests/virtual_sensor.c)
SOF, VERSION, SENSOR_THERMAL, SENSOR_RGB = 0xB6, 2, 0x01, 0x02
MIN_TEMP, MAX_TEMP = -4000, 30000
MIN_INTERVAL_MS, SILENCE_MS, BYTE_TIMEOUT_MS = 50, 1000, 20
COUNTERS = ("frame_errors", "out_of_range", "malformed", "rate_limited", "unsupported", "replay", "stale", "disconnects", "interarrival", "overflow", "timeouts", "silent")
COMPARED = ("out_of_range", "malformed", "rate_limited", "unsupported", "replay", "stale", "disconnects", "silent")


def crc8(data: bytes) -> int:
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = ((crc << 1) ^ 0x07) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc


def frame(seq: int, timestamp: int, temp: int, sensor: int = SENSOR_THERMAL, payload: bytes | None = None) -> bytes:
    body_payload = payload if payload is not None else (temp & 0xFFFF).to_bytes(2, "big")
    body = bytes([SOF, VERSION, sensor, seq & 0xFF]) + (timestamp & 0xFFFFFFFF).to_bytes(4, "big") + bytes([len(body_payload)]) + body_payload
    return body + bytes([crc8(body)])


@dataclass(frozen=True)
class Event:
    at: int
    kind: str                  # "serial" | "burst" | "tick"
    data: bytes = b""


def serial(at: int, data: bytes) -> Event:
    return Event(at, "serial", data)


def burst(at: int, data: bytes) -> Event:
    return Event(at, "burst", data)


def tick(at: int) -> Event:
    return Event(at, "tick")


def script_of(events: list[Event]) -> str:
    lines: list[str] = []
    for index, event in enumerate(events):
        lines.append(f"T {event.at}")
        if event.kind == "serial":
            lines.append("S " + event.data.hex())
        elif event.kind == "burst":
            lines.append("B " + event.data.hex())
        lines.append("Q")
        lines.append(f"M {index}")
    return "\n".join(lines) + "\n"


@dataclass
class Step:
    readings: list[int] = field(default_factory=list)
    counters: dict[str, int] = field(default_factory=dict)


def parse_output(text: str, count: int) -> list[Step]:
    steps: list[Step] = []
    current = Step()
    for line in text.splitlines():
        parts = line.split()
        if not parts:
            continue
        if parts[0] == "R":
            current.readings.append(int(parts[1]))
        elif parts[0] == "Q" and len(parts) == 1 + len(COUNTERS):
            current.counters = dict(zip(COUNTERS, (int(v) for v in parts[1:])))
        elif parts[0] == "M":
            steps.append(current)
            current = Step()
        else:
            raise RuntimeError(f"the virtual sensor link printed a line that is not part of its protocol: {line!r}")
    if len(steps) != count:
        raise RuntimeError(f"the virtual sensor link answered {len(steps)} of {count} steps")
    return steps


def _wsl_path(value: str) -> str:
    drive, rest = os.path.splitdrive(value)
    return f"/mnt/{drive[:1].lower()}{rest.replace(os.sep, '/')}" if drive else value.replace(os.sep, "/")


def build(binary: Path) -> list[str] | None:
    """Compiles the virtual sensor link and returns the command that runs it (through WSL on Windows), or None when it cannot be built here."""
    if local_build_refusal() is not None:
        return None
    flags = [*FLAGS, *(SANITIZE if os.environ.get("URTC_SANITIZE", "") == "1" else [])]
    inc = [f"-I{i}" for i in INCLUDES]
    if os.name == "nt":
        wsl = shutil.which("wsl")
        if wsl is None:
            return None
        out = _wsl_path(str(binary))
        if subprocess.run([wsl, "--cd", str(ROOT), "--", "gcc", *flags, *inc, "-o", out, *SOURCES]).returncode != 0:
            raise SystemExit("SENSOR_BENCH=FAIL the virtual sensor link did not compile")
        return [wsl, "--cd", str(ROOT), "--", out]
    cc = shutil.which("cc") or shutil.which("gcc")
    if cc is None:
        return None
    if subprocess.run([cc, *flags, *inc, "-o", str(binary), *SOURCES], cwd=ROOT).returncode != 0:
        raise SystemExit("SENSOR_BENCH=FAIL the virtual sensor link did not compile")
    return [str(binary)]


def play(prefix: list[str], events: list[Event], timeout: float = 120.0) -> list[Step]:
    done = subprocess.run(prefix, input=script_of(events), capture_output=True, text=True, timeout=timeout, check=False)
    if done.returncode != 0:
        raise RuntimeError(f"the virtual sensor link stopped with status {done.returncode}: {done.stderr.strip()[:2000]}")
    return parse_output(done.stdout, len(events))


# ---- the reference, written from the rules of the link ---------------------------------------------------------------------------------------------
@dataclass
class Reference:
    """What the link must do with a frame that reaches it whole: refuse another sensor, a payload of the wrong size or an impossible temperature, then a repeat or an
    older sequence, then frozen data, then a reading that comes too soon; accept the rest. The silence watch reports a sensor that sent nothing accepted for a second."""
    has_last: bool = False
    last_seq: int = 0
    last_ts: int = 0
    has_accepted: bool = False
    last_accept: int = 0
    silent: bool = False
    counts: dict[str, int] = field(default_factory=lambda: {name: 0 for name in COMPARED})

    def tick(self, now: int) -> None:
        if self.has_accepted and not self.silent and now - self.last_accept >= SILENCE_MS:
            self.silent = True
            self.counts["disconnects"] += 1
            self.has_last = False

    def frame_of(self, chunk: bytes) -> bytes | None:
        """The whole valid frame in a chunk that starts with noise without the start byte, or None (damaged, cut, or no start byte)."""
        start = chunk.find(bytes([SOF]))
        if start < 0:
            return None
        data = chunk[start:]
        if len(data) < 10 or data[1] != VERSION or data[8] > 16:
            return None
        total = 9 + data[8] + 1
        if len(data) < total or crc8(data[: total - 1]) != data[total - 1]:
            return None
        return data[:total]

    def receive(self, chunk: bytes, now: int) -> list[int]:
        data = self.frame_of(chunk)
        if data is None:
            return []
        sensor, seq, timestamp, length = data[2], data[3], int.from_bytes(data[4:8], "big"), data[8]
        if sensor != SENSOR_THERMAL:
            self.counts["unsupported"] += 1
            return []
        if length != 2:
            self.counts["malformed"] += 1
            return []
        temp = int.from_bytes(data[9:11], "big", signed=True)
        if not MIN_TEMP <= temp <= MAX_TEMP:
            self.counts["out_of_range"] += 1
            return []
        if self.has_last:
            step = (seq - self.last_seq) & 0xFF
            if step == 0 or step >= 128:
                self.counts["replay"] += 1
                return []
            time_step = (timestamp - self.last_ts) & 0xFFFFFFFF
            if time_step == 0 or time_step >= 0x80000000:
                self.counts["stale"] += 1
                return []
        if self.has_accepted and now - self.last_accept < MIN_INTERVAL_MS:
            self.counts["rate_limited"] += 1
            return []
        self.has_accepted = True
        self.last_accept = now
        self.has_last, self.last_seq, self.last_ts = True, seq, timestamp
        self.silent = False
        return [temp]


def reference_steps(events: list[Event]) -> list[Step]:
    ref = Reference()
    steps: list[Step] = []
    for event in events:
        ref.tick(event.at)
        readings = ref.receive(event.data, event.at) if event.kind == "serial" else []
        steps.append(Step(readings, {**ref.counts, "silent": 1 if ref.silent else 0}))
    return steps


def compare(name: str, firmware: list[Step], reference: list[Step], events: list[Event]) -> list[str]:
    problems: list[str] = []
    for index, (a, b) in enumerate(zip(firmware, reference)):
        if events[index].kind == "burst":
            continue                # a burst can overflow the ring by design; the reference has no ring
        where = f"{name} step {index} at {events[index].at} ms"
        if a.readings != b.readings:
            problems.append(f"{where}: readings differ: link {a.readings} reference {b.readings}")
        seen = {key: a.counters.get(key, -1) for key in COMPARED}
        wanted = {key: b.counters.get(key, -1) for key in COMPARED}
        if seen != wanted:
            problems.append(f"{where}: counters differ: link {seen} reference {wanted}")
        if len(problems) >= 5:
            break
    return problems


# ---- scenarios ------------------------------------------------------------------------------------------------------------------------------------
@dataclass
class Scenario:
    name: str
    about: str
    events: list[Event]
    readings: list[int] | None = None                  # every accepted reading, in order
    counters: dict[str, int] | None = None             # the counters at the end (only the keys given)
    invariant: Callable[[list[Step]], list[str]] | None = None
    reference: bool = True                             # False: a frame that comes in pieces is outside what the reference models (it takes whole frames)


def fixed_scenarios() -> list[Scenario]:
    out: list[Scenario] = []
    out.append(Scenario("happy_path", "good readings 100 ms apart are accepted in order", [
        serial(1000, frame(1, 1000, 2000)), serial(1100, frame(2, 1100, 2100)), serial(1200, frame(3, 1200, -50)), tick(1300)],
        readings=[2000, 2100, -50], counters={"out_of_range": 0, "rate_limited": 0, "replay": 0, "stale": 0, "malformed": 0, "silent": 0}))
    out.append(Scenario("range_edges", "the limits of the range are accepted and one hundredth beyond them is refused", [
        serial(100, frame(1, 100, MIN_TEMP)), serial(200, frame(2, 200, MAX_TEMP)), serial(300, frame(3, 300, MAX_TEMP + 1)), serial(400, frame(4, 400, MIN_TEMP - 1))],
        readings=[MIN_TEMP, MAX_TEMP], counters={"out_of_range": 2}))
    out.append(Scenario("wrong_payload_size", "a reading of one or three bytes is a malformed frame, not an impossible temperature", [
        serial(100, frame(1, 100, 0, payload=b"\x07")), serial(200, frame(2, 200, 0, payload=b"\x07\xd0\x00"))],
        readings=[], counters={"malformed": 2, "out_of_range": 0}))
    out.append(Scenario("other_sensor", "a frame from the colour trigger or from an unknown sensor is not read", [
        serial(100, frame(1, 100, 2000, sensor=SENSOR_RGB)), serial(200, frame(2, 200, 2000, sensor=0x7F))],
        readings=[], counters={"unsupported": 2}))
    out.append(Scenario("repeated_frame", "the same frame twice is read once", [serial(100, frame(5, 100, 2000)), serial(200, frame(5, 100, 2000))],
        readings=[2000], counters={"replay": 1}))
    out.append(Scenario("older_frame", "a frame with an older sequence is refused", [serial(100, frame(9, 100, 2000)), serial(200, frame(8, 200, 2100))],
        readings=[2000], counters={"replay": 1}))
    out.append(Scenario("sequence_wraps", "the sequence goes from 255 to 0 and is still newer", [serial(100, frame(255, 100, 2000)), serial(200, frame(0, 200, 2100))],
        readings=[2000, 2100], counters={"replay": 0}))
    out.append(Scenario("frozen_data", "a new sequence with the same sensor time is a sensor sending frozen data", [serial(100, frame(1, 500, 2000)), serial(200, frame(2, 500, 2100))],
        readings=[2000], counters={"stale": 1}))
    out.append(Scenario("too_fast", "a reading 10 ms after the previous one is throttled; one 50 ms later is read", [
        serial(100, frame(1, 100, 2000)), serial(110, frame(2, 110, 2100)), serial(150, frame(3, 150, 2200))],
        readings=[2000, 2200], counters={"rate_limited": 1}))
    good = frame(1, 100, 2000)
    damaged = bytearray(good)
    damaged[10] ^= 0x40
    out.append(Scenario("damaged_frame", "a frame with a changed byte is never read and counts as an error", [serial(100, bytes(damaged)), serial(200, frame(2, 200, 2100))],
        readings=[2100]))
    out.append(Scenario("cut_frame", "the first half of a frame that is never finished is dropped by the timeout and the next frame is read", [
        serial(100, good[:5]), serial(200, frame(2, 200, 2100))], readings=[2100], counters={"timeouts": 1}))
    out.append(Scenario("frame_in_two_pieces", "the halves of a frame that come within the timeout make one reading", [serial(100, good[:5]), serial(110, good[5:])], readings=[2000], reference=False))
    out.append(Scenario("noise_between_frames", "bytes that are not a start byte are skipped without a count", [
        serial(100, bytes([0x00, 0x13, 0xFF, 0x42]) + good), serial(200, frame(2, 200, 2100))], readings=[2000, 2100], counters={"frame_errors": 0}))
    out.append(Scenario("silence_and_return", "a second without an accepted frame is reported once; the sensor may then start its numbering again", [
        serial(100, frame(40, 100, 2000)), tick(600), tick(1100), tick(2000), serial(2100, frame(1, 50, 2100)), tick(2200)],
        readings=[2000, 2100], counters={"disconnects": 1, "silent": 0, "replay": 0}))
    out.append(Scenario("silence_stays_reported_once", "the same silence is not counted twice", [serial(100, frame(1, 100, 2000)), tick(1100), tick(5000), tick(9000)],
        readings=[2000], counters={"disconnects": 1, "silent": 1}))
    return out


def random_scenario(seed: int, count: int) -> Scenario:
    """Seeded random run: readings of a sensor with faults injected (damaged, cut, noisy, repeated, frozen, out of range, another sensor, lost, late). Every frame comes
    at least 25 ms after the previous one, so a half frame is always dropped by the timeout before the next one starts."""
    rng = random.Random(seed)
    events: list[Event] = []
    at, seq, ts = 1000, 0, 1000
    for _ in range(count):
        at += rng.choice([25, 30, 50, 60, 120, 400, 1200])
        ts += rng.choice([20, 100, 400])
        seq = (seq + rng.choice([1, 1, 1, 1, 2])) & 0xFF
        if seq == SOF:
            seq = (seq + 1) & 0xFF
        temp = rng.choice([-4000, -1, 0, 2000, 2600, 9000, 30000, 30001, -4001, 31000])
        fault = rng.choice(["none"] * 7 + ["damage", "cut", "noise", "repeat", "frozen", "other", "lose", "tick", "size"])
        data = frame(seq, ts, temp)
        if fault == "frozen":
            data = frame(seq, ts - 100, temp)
        elif fault == "other":
            data = frame(seq, ts, temp, sensor=rng.choice([SENSOR_RGB, 0x55]))
        elif fault == "size":
            data = frame(seq, ts, temp, payload=bytes(rng.randrange(0, 4)))
        elif fault == "damage":
            bad = bytearray(data)
            bad[rng.randrange(len(bad))] ^= 1 << rng.randrange(8)
            data = bytes(bad)
        elif fault == "cut":
            data = data[: rng.randrange(1, len(data))]
        elif fault == "noise":
            data = bytes(rng.choice([b for b in range(256) if b != SOF]) for _ in range(rng.randrange(1, 6))) + data
        if fault in ("lose", "tick"):
            events.append(tick(at))
            continue
        events.append(serial(at, data))
        if fault == "repeat":
            at += 25
            events.append(serial(at, data))
    return Scenario(f"random_{seed}", f"{count} random readings with injected faults (seed {seed})", events, invariant=random_invariants)


def random_invariants(steps: list[Step]) -> list[str]:
    """Whatever the sensor sent, an accepted reading is inside the range and the counters never go down."""
    problems: list[str] = []
    previous = {name: 0 for name in COMPARED if name != "silent"}
    for index, step in enumerate(steps):
        for reading in step.readings:
            if not MIN_TEMP <= reading <= MAX_TEMP:
                problems.append(f"step {index}: the reading {reading} is outside the range and was accepted")
        for name in previous:
            if step.counters.get(name, 0) < previous[name]:
                problems.append(f"step {index}: the counter {name} went down")
            previous[name] = step.counters.get(name, 0)
        if len(problems) >= 5:
            break
    return problems


def check_expectations(scenario: Scenario, steps: list[Step]) -> list[str]:
    problems: list[str] = []
    if scenario.readings is not None:
        got = [reading for step in steps for reading in step.readings]
        if got != scenario.readings:
            problems.append(f"{scenario.name}: readings {got} must be {scenario.readings}")
    for key, value in (scenario.counters or {}).items():
        if steps[-1].counters.get(key) != value:
            problems.append(f"{scenario.name}: the counter {key} ends at {steps[-1].counters.get(key)} and must end at {value}")
    if scenario.invariant is not None:
        problems.extend(f"{scenario.name}: {message}" for message in scenario.invariant(steps))
    return problems


def burst_overflow_check(prefix: list[str]) -> list[str]:
    """Four hundred bytes arriving before the main loop polls: the ring keeps what fits, the loss is counted, and the next good frame is still read."""
    noise = bytes((index * 37) % 251 for index in range(400))      # no byte of it is the start byte
    steps = play(prefix, [burst(100, noise), serial(300, frame(1, 300, 2000))])
    problems: list[str] = []
    if steps[0].counters.get("overflow", 0) == 0:
        problems.append("burst_overflow: 400 bytes at once must overflow the ring and be counted")
    if steps[-1].readings != [2000]:
        problems.append(f"burst_overflow: a good frame after the burst must still be read, got {steps[-1].readings}")
    return problems


def run_all(prefix: list[str], only: list[str], seed: int, count: int) -> list[str]:
    scenarios = [*fixed_scenarios(), random_scenario(seed, count), random_scenario(seed + 1, count)]
    problems: list[str] = []
    ran = 0
    for scenario in scenarios:
        if only and scenario.name not in only:
            continue
        ran += 1
        steps = play(prefix, scenario.events)
        found = check_expectations(scenario, steps) + (compare(scenario.name, steps, reference_steps(scenario.events), scenario.events) if scenario.reference else [])
        print(f"SENSOR_BENCH {scenario.name}: {'FAIL' if found else 'PASS'} ({len(scenario.events)} events, compared with the reference)")
        problems.extend(found)
    if not only or "burst_overflow" in only:
        ran += 1
        found = burst_overflow_check(prefix)
        print(f"SENSOR_BENCH burst_overflow: {'FAIL' if found else 'PASS'}")
        problems.extend(found)
    if ran == 0:
        problems.append("no scenario has that name")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Play scenarios with faults through the real receive path of the thermal sensor link compiled for the host.")
    parser.add_argument("--list", action="store_true", help="list the scenarios")
    parser.add_argument("--only", action="append", default=[], help="run only this scenario (repeatable)")
    parser.add_argument("--seed", type=int, default=4242, help="seed of the random scenarios")
    parser.add_argument("--events", type=int, default=1500, help="readings in each random scenario")
    parser.add_argument("--dump", metavar="DIR", help="write the script of every scenario to DIR")
    parser.add_argument("--replay", metavar="FILE", help="play a recorded script through the virtual sensor link and print its answers")
    parser.add_argument("--build-dir", metavar="DIR", help="where the binary goes (default: a temporary folder)")
    args = parser.parse_args(argv)

    if args.list:
        for scenario in [*fixed_scenarios(), random_scenario(args.seed, args.events)]:
            print(f"{scenario.name}: {scenario.about}")
        print("burst_overflow: more bytes than the receive ring holds arrive before the main loop polls")
        return 0
    if args.dump:
        target = Path(args.dump)
        target.mkdir(parents=True, exist_ok=True)
        for scenario in [*fixed_scenarios(), random_scenario(args.seed, args.events)]:
            (target / f"{scenario.name}.txt").write_text(script_of(scenario.events), encoding="utf-8", newline="\n")
        print(f"SENSOR_BENCH_DUMP={target}")
        return 0

    with tempfile.TemporaryDirectory(dir=args.build_dir) as directory:
        prefix = build(Path(directory) / "virtual_sensor")
        if prefix is None:
            print("SENSOR_BENCH=SKIPPED no host C compiler, or local builds are locked (ALLOW_LOCAL_BUILD=1 allows them)")
            return 2
        if args.replay:
            done = subprocess.run(prefix, input=Path(args.replay).read_text(encoding="utf-8"), capture_output=True, text=True, timeout=300, check=False)
            sys.stdout.write(done.stdout)
            return done.returncode
        problems = run_all(prefix, args.only, args.seed, args.events)
    for problem in problems:
        print(f"SENSOR_BENCH problem: {problem}")
    print("SENSOR_BENCH=PASS" if not problems else f"SENSOR_BENCH=FAIL {len(problems)} problem(s)")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
