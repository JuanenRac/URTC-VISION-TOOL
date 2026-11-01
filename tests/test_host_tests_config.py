"""tools/host_tests.json is the one list of host suites that the shared executor (tools/run_host_tests.py) builds and runs."""
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import run_host_tests as runner  # noqa: E402


class HostSuiteConfigTests(unittest.TestCase):
    def test_every_file_the_suites_name_exists_and_the_test_is_not_linked_twice(self):
        self.assertTrue(runner.SUITES)
        for suite in runner.SUITES:
            for source in (suite.test, *suite.sources):
                self.assertTrue((ROOT / source).is_file(), f"{suite.name}: {source}")
            self.assertNotIn(suite.test, suite.sources)
            self.assertEqual(len(suite.sources), len(set(suite.sources)))
            for include in suite.includes:
                self.assertTrue((ROOT / include).is_dir(), f"{suite.name}: {include}")

    def test_every_firmware_source_that_is_not_the_target_entry_is_compiled_by_a_suite(self):
        compiled = {source for suite in runner.SUITES for source in suite.sources}
        entry = {name for name in runner.all_firmware_sources() if "startup" in name or name.endswith("/main.c")}
        self.assertEqual(sorted(set(runner.all_firmware_sources()) - compiled - entry), [])

    def test_the_sanitizers_follow_the_ci_variable(self):
        suite = runner.SUITES[0]
        saved = os.environ.get("URTC_SANITIZE")
        try:
            os.environ["URTC_SANITIZE"] = "0"
            self.assertNotIn("-fsanitize=address,undefined", runner.command(suite, "cc", Path("out")))
            os.environ["URTC_SANITIZE"] = "1"
            self.assertIn("-fsanitize=address,undefined", runner.command(suite, "cc", Path("out")))
        finally:
            if saved is None:
                os.environ.pop("URTC_SANITIZE", None)
            else:
                os.environ["URTC_SANITIZE"] = saved

    def test_the_cmake_file_has_one_test_per_suite(self):
        text = runner.cmake_lists(list(runner.SUITES), "cc")
        self.assertEqual(text.count("add_test("), len(runner.SUITES))
        self.assertIn("enable_testing()", text)


if __name__ == "__main__":
    unittest.main()
