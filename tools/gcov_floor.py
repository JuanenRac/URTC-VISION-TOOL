#!/usr/bin/env python3
# =============================================================================
# URTC-VISION-TOOL - tools/gcov_floor.py
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""Fails when the host tests execute less of the firmware sources than a floor.

    python tools/gcov_floor.py FLOOR BUILD_DIR [SOURCE_PREFIX]

The host tests are built with ``--coverage`` (build_firmware.sh does it when ``URTC_COVERAGE_FLOOR`` is set); this
runs ``gcov`` on the ``.gcda`` files in BUILD_DIR and adds up the executed and the executable lines of the files
whose path starts with SOURCE_PREFIX (default ``src/``). Tests and headers of the tests are not counted. The floor is
a percentage; the CI sets it eight points under what is measured so a real drop fails and noise does not.

Standard library only.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_FILE = re.compile(r"^File '(.+)'$")
_LINES = re.compile(r"^Lines executed:([0-9.]+)% of (\d+)$")


def parse_gcov(output: str, prefix: str = "src/") -> dict[str, tuple[int, int]]:
    """{file: (executed lines, executable lines)} for the files of ``gcov -n`` output whose name starts with ``prefix``."""
    result: dict[str, tuple[int, int]] = {}
    current: str | None = None
    for line in output.splitlines():
        match = _FILE.match(line.strip())
        if match:
            current = match.group(1).replace("\\", "/")
            continue
        match = _LINES.match(line.strip())
        if match and current is not None:
            total = int(match.group(2))
            executed = round(float(match.group(1)) * total / 100)
            if current.startswith(prefix) and current.endswith(".c"):
                done, count = result.get(current, (0, 0))
                result[current] = (max(done, executed), max(count, total))
            current = None
    return result


def percent(files: dict[str, tuple[int, int]]) -> float:
    total = sum(count for _, count in files.values())
    return 100.0 * sum(done for done, _ in files.values()) / total if total else 0.0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) not in (2, 3):
        print(__doc__)
        return 2
    try:
        floor = float(args[0])
    except ValueError:
        print(f"COVERAGE=FAIL the floor {args[0]!r} is not a number")
        return 2
    build = Path(args[1])
    prefix = args[2] if len(args) == 3 else "src/"
    gcda = sorted(build.glob("*.gcda"))
    if not gcda:
        print(f"COVERAGE=FAIL no .gcda file in {build}: build the host tests with --coverage and run them first")
        return 1
    run = subprocess.run(["gcov", "-n", "-o", str(build), *[str(p) for p in gcda]], cwd=ROOT, capture_output=True, text=True, check=False)
    files = parse_gcov(run.stdout, prefix)
    if not files:
        print("COVERAGE=FAIL gcov reported no source file under " + prefix)
        return 1
    value = percent(files)
    for name in sorted(files):
        done, count = files[name]
        print(f"  {name}: {done}/{count} lines")
    if value + 1e-9 < floor:
        print(f"COVERAGE=FAIL {value:.2f}% of the lines of {prefix} run by the host tests, the floor is {floor:g}%")
        return 1
    print(f"COVERAGE=PASS {value:.2f}% of the lines of {prefix} run by the host tests (floor {floor:g}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
