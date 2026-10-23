# =============================================================================
# URTC-VISION-TOOL - tests/test_gcov_floor.py
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""The coverage floor of the host tests: reading the gcov summary and failing under the floor."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import gcov_floor  # noqa: E402

SAMPLE = """File 'src/a.c'
Lines executed:50.00% of 10
Creating 'a.c.gcov'

File 'src/b.c'
Lines executed:100.00% of 30
Creating 'b.c.gcov'

File 'src/urtc_crc8.h'
Lines executed:100.00% of 12

File 'tests/test_a.c'
Lines executed:100.00% of 99

File '/usr/include/stdio.h'
Lines executed:0.00% of 5
"""


class ParseTests(unittest.TestCase):
    def test_only_the_sources_under_the_prefix_count(self):
        files = gcov_floor.parse_gcov(SAMPLE)
        self.assertEqual(files, {"src/a.c": (5, 10), "src/b.c": (30, 30)})

    def test_the_share_is_over_all_the_lines(self):
        self.assertAlmostEqual(gcov_floor.percent(gcov_floor.parse_gcov(SAMPLE)), 87.5)
        self.assertEqual(gcov_floor.percent({}), 0.0)

    def test_a_file_seen_twice_keeps_the_best_run(self):
        text = "File 'src/a.c'\nLines executed:10.00% of 10\nFile 'src/a.c'\nLines executed:80.00% of 10\n"
        self.assertEqual(gcov_floor.parse_gcov(text), {"src/a.c": (8, 10)})


class CommandTests(unittest.TestCase):
    def test_a_bad_floor_or_a_missing_build_is_a_failure_not_a_pass(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(gcov_floor.main(["x", folder]), 2)
            self.assertEqual(gcov_floor.main([]), 2)
            self.assertEqual(gcov_floor.main(["80", folder]), 1)  # no .gcda file in it


if __name__ == "__main__":
    unittest.main()
