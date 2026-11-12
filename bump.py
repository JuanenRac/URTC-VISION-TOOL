#!/usr/bin/env python3
# =============================================================================
# URTC-VISION-TOOL - bump.py
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""Raises this project's version by one step of the ecosystem odometer, explicitly.

Building never changes a version; run this first when a new version is wanted:

    python bump.py             raise the version (native source, urtc.project.json, CHANGELOG.md heading)
    python bump.py --dry-run   show the next version, write nothing
    python bump.py --companion raise the version of the Python vision_companion package (its own, independent version)
                               on the same odometer; add --dry-run to only show it. The package version lives in
                               src/vision_companion/vision_companion/__init__.py and nowhere else.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
COMPANION_INIT = ROOT / "src" / "vision_companion" / "vision_companion" / "__init__.py"
COMPANION_LINE = re.compile(r'(?m)^(__version__\s*=\s*")(\d+)\.(\d+)\.(\d+)(")')


def next_companion_version(major: int, minor: int, patch: int) -> tuple[int, int, int]:
    """The odometer of the ecosystem: the patch carries into the minor at 9 and the minor into the major."""
    patch += 1
    if patch > 9:
        patch, minor = 0, minor + 1
    if minor > 9:
        minor, major = 0, major + 1
    return major, minor, patch


def bump_companion(path: Path = COMPANION_INIT, dry_run: bool = False) -> str:
    """Raises `__version__` of the companion package by one step and returns the new version; writes nothing with dry_run."""
    text = path.read_bytes().decode("utf-8")   # bytes, so that the line endings of the file are not translated
    matches = COMPANION_LINE.findall(text)
    if len(matches) != 1:
        raise SystemExit(f"{path.name}: expected exactly one __version__ = \"MAJOR.MINOR.PATCH\" line, found {len(matches)}")
    major, minor, patch = next_companion_version(int(matches[0][1]), int(matches[0][2]), int(matches[0][3]))
    new = f"{major}.{minor}.{patch}"
    if not dry_run:
        updated = COMPANION_LINE.sub(lambda m: f"{m.group(1)}{new}{m.group(5)}", text, count=1)
        path.write_bytes(updated.encode("utf-8"))   # bytes: the line endings of the file stay as they are
    return new


def run(*command: str) -> None:
    result = subprocess.run([sys.executable, *command], cwd=ROOT)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main(argv: list[str]) -> int:
    if "--companion" in argv:
        dry = "--dry-run" in argv
        print(bump_companion(dry_run=dry))
        return 0
    if "--dry-run" in argv:
        import json
        manifest = json.loads((ROOT / "urtc.project.json").read_text(encoding="utf-8"))
        print(f"current version {manifest['version']}; --dry-run writes nothing")
        return 0
    run("bump_version.py", "src/firmware_common.h", "FIRMWARE_VERSION")
    run("bump_manifest_version.py", "--sync")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
