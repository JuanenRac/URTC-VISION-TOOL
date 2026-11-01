#!/usr/bin/env python3
# =============================================================================
# URTC-VISION-TOOL - check that the vendored Melexis drivers have not drifted
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""The MLX9064x drivers in third_party/ are copies of the ones the URTC firmware compiles.

URTC once let its two copies drift (only one had the bounded data-ready wait and the cap on the scale loop). To keep that from happening
here, third_party/melexis.lock.json holds the SHA-256 of every vendored file (line ends do not count) and this script fails when a file
differs, is missing or is not listed. When a checkout of URTC is next to this repository (or is named by URTC_DIR) it also compares each
file with the copy of the expansion slave of URTC, which is the reference, so a fix made there is reported here.

    python tools/check_shared_drivers.py            check (exit 1 on any difference)
    python tools/check_shared_drivers.py --update   rewrite the lock from the files (after copying a fixed driver from URTC)
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / "third_party"
LOCK = VENDOR / "melexis.lock.json"
VENDOR_DIRS = ("melexis_mlx90640", "melexis_mlx90641", "melexis_mlx90642")
REFERENCE_SUBPATH = Path("src") / "F303-slave"


def digest(path: Path) -> str:
    """SHA-256 of the file with CRLF read as LF: a checkout may hold the same file with either."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def vendored_files() -> list[str]:
    found: list[str] = []
    for folder in VENDOR_DIRS:
        found.extend(f"{folder}/{p.name}" for p in sorted((VENDOR / folder).iterdir()) if p.is_file())
    return found


def reference_root() -> Path | None:
    """The checkout of URTC to compare with, if there is one."""
    named = os.environ.get("URTC_DIR")
    for candidate in ([Path(named)] if named else []) + [ROOT.parent / "URTC"]:
        if (candidate / REFERENCE_SUBPATH).is_dir():
            return candidate / REFERENCE_SUBPATH
    return None


def compare_with_lock() -> list[str]:
    problems: list[str] = []
    lock = json.loads(LOCK.read_text(encoding="utf-8"))["files"]
    files = vendored_files()
    for rel in files:
        if rel not in lock:
            problems.append(f"NOT LISTED: third_party/{rel} is not in melexis.lock.json")
        elif digest(VENDOR / rel) != lock[rel]:
            problems.append(f"DIFFERS FROM THE LOCK: third_party/{rel}")
    for rel in lock:
        if rel not in files:
            problems.append(f"MISSING: third_party/{rel} is in the lock but not on disk")
    return problems


def compare_with_reference(reference: Path) -> list[str]:
    problems: list[str] = []
    for rel in vendored_files():
        other = reference / rel
        if not other.is_file():
            problems.append(f"NOT IN URTC: {rel} has no counterpart in the reference")
        elif digest(other) != digest(VENDOR / rel):
            problems.append(f"DIFFERS FROM URTC: third_party/{rel} vs {REFERENCE_SUBPATH.as_posix()}/{rel}")
    return problems


def write_lock() -> None:
    files = {rel: digest(VENDOR / rel) for rel in vendored_files()}
    LOCK.write_text(json.dumps({"format": 1, "reference": "URTC src/F303-slave", "files": files}, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    if "--update" in argv:
        write_lock()
        print(f"{len(vendored_files())} vendored Melexis driver files written to the lock")
        return 0
    problems = compare_with_lock()
    reference = reference_root()
    if reference is not None:
        problems += compare_with_reference(reference)
    for line in problems:
        print(line)
    if problems:
        print("Copy the fixed driver from URTC (src/F303-slave) and run this script with --update.")
        return 1
    where = "and with the copy in URTC" if reference is not None else "(no checkout of URTC next to this one: lock only)"
    print(f"{len(vendored_files())} vendored Melexis driver files match the lock {where}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
