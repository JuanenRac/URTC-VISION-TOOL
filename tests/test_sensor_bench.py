"""The software bench of the sensor link (tools/sensor_bench.py): the scripts it writes, how it reads the answers, its reference, and the run against the virtual link when a compiler is there."""
import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import sensor_bench as bench  # noqa: E402


class FramesTests(unittest.TestCase):
    def test_a_frame_has_the_layout_of_the_sensor_link(self):
        data = bench.frame(5, 0x01020304, 2000)
        self.assertEqual(data[:9], bytes([0xB6, 2, 1, 5, 1, 2, 3, 4, 2]))
        self.assertEqual(data[9:11], (2000).to_bytes(2, "big"))
        self.assertEqual(data[11], bench.crc8(data[:11]))

    def test_a_negative_temperature_is_two_bytes_of_a_signed_number(self):
        self.assertEqual(bench.frame(1, 1, -50)[9:11], (65536 - 50).to_bytes(2, "big"))


class ScriptTests(unittest.TestCase):
    def test_every_event_is_a_clock_line_a_command_a_counters_request_and_a_marker(self):
        lines = bench.script_of([bench.serial(10, b"\xb6\x02"), bench.burst(20, b"\x01"), bench.tick(30)]).splitlines()
        self.assertEqual(lines[:4], ["T 10", "S b602", "Q", "M 0"])
        self.assertIn("B 01", lines)
        self.assertEqual(lines[-3:], ["T 30", "Q", "M 2"])

    def test_the_answers_are_split_at_the_markers(self):
        counters = " ".join(["0"] * len(bench.COUNTERS))
        steps = bench.parse_output(f"R 2000\nR -5\nQ {counters}\nM 0\nQ {counters}\nM 1\n", 2)
        self.assertEqual(steps[0].readings, [2000, -5])
        self.assertEqual(steps[1].readings, [])
        self.assertEqual(set(steps[0].counters), set(bench.COUNTERS))

    def test_a_line_outside_the_protocol_or_a_missing_step_is_an_error(self):
        with self.assertRaises(RuntimeError):
            bench.parse_output("X what\nM 0\n", 1)
        with self.assertRaises(RuntimeError):
            bench.parse_output("M 0\n", 2)


class ReferenceTests(unittest.TestCase):
    def test_the_reference_follows_the_rules_of_the_link(self):
        ref = bench.Reference()
        self.assertEqual(ref.receive(bench.frame(1, 100, 2000), 100), [2000])
        self.assertEqual(ref.receive(bench.frame(1, 100, 2000), 200), [])            # repeated
        self.assertEqual(ref.receive(bench.frame(2, 100, 2100), 300), [])            # frozen
        self.assertEqual(ref.receive(bench.frame(3, 300, 2100), 320), [2100])
        self.assertEqual(ref.receive(bench.frame(4, 400, 2200), 330), [])            # too fast
        self.assertEqual(ref.receive(bench.frame(4, 400, 2200), 400), [2200])
        self.assertEqual(ref.receive(bench.frame(5, 500, 40000 - 65536), 500), [])   # impossible temperature (as a signed number)
        self.assertEqual({k: v for k, v in ref.counts.items() if v}, {"replay": 1, "stale": 1, "rate_limited": 1, "out_of_range": 1})

    def test_a_silence_is_counted_once_and_lets_the_numbering_start_again(self):
        ref = bench.Reference()
        ref.receive(bench.frame(40, 100, 2000), 100)
        ref.tick(1100)
        ref.tick(5000)
        self.assertEqual(ref.counts["disconnects"], 1)
        self.assertEqual(ref.receive(bench.frame(1, 50, 2100), 5100), [2100])
        self.assertFalse(ref.silent)

    def test_the_hand_written_expectations_hold_for_the_reference_too(self):
        for scenario in [*bench.fixed_scenarios(), bench.random_scenario(11, 300)]:
            if not scenario.reference:
                continue
            problems = [p for p in bench.check_expectations(scenario, bench.reference_steps(scenario.events)) if "timeouts" not in p and "frame_errors" not in p]
            self.assertEqual(problems, [], scenario.name)


class ScenarioTests(unittest.TestCase):
    def test_the_scenarios_have_distinct_names_and_the_clock_never_goes_back(self):
        scenarios = [*bench.fixed_scenarios(), bench.random_scenario(1, 200)]
        self.assertEqual(len({s.name for s in scenarios}), len(scenarios))
        for scenario in scenarios:
            times = [event.at for event in scenario.events]
            self.assertEqual(times, sorted(times), scenario.name)

    def test_the_random_scenarios_repeat_for_a_seed_and_differ_between_seeds(self):
        self.assertEqual(bench.random_scenario(3, 100).events, bench.random_scenario(3, 100).events)
        self.assertNotEqual(bench.random_scenario(3, 100).events, bench.random_scenario(4, 100).events)

    def test_a_difference_between_the_link_and_the_reference_is_reported(self):
        events = [bench.tick(0)]
        counters = {name: 0 for name in bench.COMPARED}
        a = bench.Step([2000], dict(counters))
        self.assertEqual(bench.compare("x", [a], [bench.Step([2000], dict(counters))], events), [])
        self.assertEqual(len(bench.compare("x", [a], [bench.Step([], {**counters, "replay": 1})], events)), 2)

    def test_the_invariants_see_a_reading_out_of_range_and_a_counter_that_goes_down(self):
        counters = {name: 0 for name in bench.COMPARED}
        self.assertTrue(bench.random_invariants([bench.Step([30001], dict(counters))]))
        self.assertTrue(bench.random_invariants([bench.Step([], {**counters, "replay": 2}), bench.Step([], {**counters, "replay": 1})]))
        self.assertEqual(bench.random_invariants([bench.Step([30000], dict(counters))]), [])

    def test_an_expectation_that_is_not_met_is_reported(self):
        scenario = bench.Scenario("x", "", [], readings=[1], counters={"replay": 1})
        self.assertEqual(len(bench.check_expectations(scenario, [bench.Step([2], {"replay": 0})])), 2)


class CommandLineTests(unittest.TestCase):
    def test_list_names_every_scenario_and_builds_nothing(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(bench.main(["--list"]), 0)
        for scenario in bench.fixed_scenarios():
            self.assertIn(scenario.name + ":", out.getvalue())

    def test_dump_writes_one_script_per_scenario(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(bench.main(["--dump", directory, "--events", "20"]), 0)
            self.assertTrue((Path(directory) / "happy_path.txt").read_text(encoding="utf-8").startswith("T 1000\n"))

    def test_without_a_compiler_it_says_skipped(self):
        original = bench.build
        bench.build = lambda binary: None
        try:
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(bench.main([]), 2)
            self.assertIn("SKIPPED", out.getvalue())
        finally:
            bench.build = original


class RealLinkTests(unittest.TestCase):
    @unittest.skipIf(os.name == "nt", "the virtual link is built on Linux (the CI); on Windows run tools/sensor_bench.py with WSL")
    def test_every_scenario_passes_against_the_real_receive_path(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()) as out:
            status = bench.main(["--build-dir", directory, "--events", "400"])
        if status == 2:
            self.skipTest("no host C compiler, or local builds are off (ALLOW_LOCAL_BUILD=1 allows them)")
        self.assertEqual(status, 0, out.getvalue()[-3000:])


if __name__ == "__main__":
    unittest.main()
