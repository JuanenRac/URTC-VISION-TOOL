"""The Melexis drivers vendored in third_party/ match their lock and the copy URTC compiles."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import check_shared_drivers as drivers  # noqa: E402


class VendoredDriverTests(unittest.TestCase):
    def test_the_lock_names_every_vendored_file_and_nothing_else(self):
        lock = json.loads(drivers.LOCK.read_text(encoding="utf-8"))["files"]
        self.assertEqual(sorted(lock), sorted(drivers.vendored_files()))
        self.assertEqual(len(drivers.VENDOR_DIRS), 3)

    def test_every_driver_keeps_the_licence_it_came_with(self):
        for folder in drivers.VENDOR_DIRS:
            self.assertTrue((drivers.VENDOR / folder / "LICENSE_MELEXIS_APACHE2.0").is_file(), folder)

    def test_the_files_match_the_lock(self):
        self.assertEqual(drivers.compare_with_lock(), [])

    def test_the_files_match_urtc_when_it_is_there(self):
        reference = drivers.reference_root()
        if reference is None:
            self.skipTest("no checkout of URTC next to this repository")
        self.assertEqual(drivers.compare_with_reference(reference), [])

    def test_a_changed_file_is_reported(self):
        with tempfile.TemporaryDirectory() as scratch:
            copy = Path(scratch) / "third_party"
            shutil.copytree(drivers.VENDOR, copy)
            target = copy / "melexis_mlx90640" / "MLX90640_API.c"
            target.write_bytes(target.read_bytes() + b"\n/* drift */\n")
            (copy / "melexis_mlx90641" / "extra.c").write_text("int x;\n", encoding="utf-8")
            (copy / "melexis_mlx90642" / "MLX90642.h").unlink()
            old_vendor, old_lock = drivers.VENDOR, drivers.LOCK
            drivers.VENDOR, drivers.LOCK = copy, copy / "melexis.lock.json"
            try:
                found = drivers.compare_with_lock()
            finally:
                drivers.VENDOR, drivers.LOCK = old_vendor, old_lock
        self.assertTrue(any(line.startswith("DIFFERS FROM THE LOCK") and "MLX90640_API.c" in line for line in found))
        self.assertTrue(any(line.startswith("NOT LISTED") and "extra.c" in line for line in found))
        self.assertTrue(any(line.startswith("MISSING") and "MLX90642.h" in line for line in found))

    def test_line_ends_do_not_count(self):
        with tempfile.TemporaryDirectory() as scratch:
            a, b = Path(scratch) / "a", Path(scratch) / "b"
            a.write_bytes(b"one\r\ntwo\r\n")
            b.write_bytes(b"one\ntwo\n")
            self.assertEqual(drivers.digest(a), drivers.digest(b))


if __name__ == "__main__":
    unittest.main()
