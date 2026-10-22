# =============================================================================
# URTC-VISION-TOOL - vision_companion tests: test_inspection.py
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""Thermal inspection of components, the export of the ROI series and the check of the sensor."""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

from vision_companion import cli, export, inspection, sensor_drift

W, H = 640, 480


def frame_with(values: dict[tuple[int, int, int, int], float], base: float = 24.0) -> np.ndarray:
    """A 32x24 thermal frame at `base` with rectangular areas (thermal pixels x0, y0, x1, y1) at other temperatures."""
    frame = np.full((24, 32), base, dtype=np.float32)
    for (x0, y0, x1, y1), value in values.items():
        frame[y0:y1, x0:x1] = value
    return frame


def plan(**overrides) -> dict:
    data = {
        "schema": 1,
        "profile": {"name": "after reflow", "ambient_c": 24.0, "rules": {
            "joint": {"expected_c": 60.0, "tolerance_c": 8.0},
            "ic": {"max_c": 85.0, "max_rise_c": 55.0},
            "heatsink": {"min_rise_c": 10.0},
        }},
        "components": [
            {"ref": "J1", "kind": "joint", "roi": [0, 0, 100, 100], "task": "reflow"},
            {"ref": "U1", "kind": "ic", "roi": [320, 240, 420, 340], "task": "reflow"},
            {"ref": "HS1", "kind": "heatsink", "roi": [540, 380, 640, 480]},
        ],
    }
    data.update(overrides)
    return data


# thermal pixel areas matching those regions: 640x480 -> 32x24 is 20 px per thermal pixel
J1, U1, HS1 = (0, 0, 5, 5), (16, 12, 21, 17), (27, 19, 32, 24)


def test_good_parts_pass() -> None:
    profile, components = inspection.plan_from_dict(plan())
    report = inspection.inspect(frame_with({J1: 60.0, U1: 70.0, HS1: 40.0}), components, profile, W, H)
    assert report.overall == inspection.PASS
    assert [r.verdict for r in report.results] == [inspection.OK] * 3


def test_a_cold_joint_and_a_hot_part_fail_with_reasons() -> None:
    profile, components = inspection.plan_from_dict(plan())
    report = inspection.inspect(frame_with({J1: 40.0, U1: 95.0, HS1: 40.0}), components, profile, W, H)
    verdicts = {r.ref: r for r in report.results}
    assert report.overall == inspection.FAIL
    assert verdicts["J1"].verdict == inspection.COLD and "below the expected" in verdicts["J1"].reasons[0]
    assert verdicts["U1"].verdict == inspection.HOT
    assert any("above the maximum" in text for text in verdicts["U1"].reasons)
    assert verdicts["HS1"].verdict == inspection.OK


def test_a_joint_that_is_too_hot_is_hot_and_a_part_that_did_not_heat_is_cold() -> None:
    profile, components = inspection.plan_from_dict(plan())
    report = inspection.inspect(frame_with({J1: 80.0, U1: 60.0, HS1: 26.0}), components, profile, W, H)
    verdicts = {r.ref: r.verdict for r in report.results}
    assert verdicts == {"J1": inspection.HOT, "U1": inspection.OK, "HS1": inspection.COLD}


def test_the_ambient_is_the_median_of_the_frame_when_the_profile_gives_none() -> None:
    data = plan()
    data["profile"]["ambient_c"] = None
    profile, components = inspection.plan_from_dict(data)
    report = inspection.inspect(frame_with({J1: 60.0, U1: 70.0, HS1: 40.0}, base=24.0), components, profile, W, H)
    assert report.ambient_c == pytest.approx(24.0)


def test_a_region_without_data_is_never_ok() -> None:
    profile, components = inspection.plan_from_dict(plan())
    frame = frame_with({J1: 60.0, U1: 70.0, HS1: 40.0})
    frame[12:17, 16:21] = np.nan
    report = inspection.inspect(frame, components, profile, W, H)
    assert {r.ref: r.verdict for r in report.results}["U1"] == inspection.NO_DATA
    assert report.overall == inspection.INCOMPLETE
    document = inspection.report_to_dict(report)
    json.dumps(document)       # NaN must not reach the JSON
    assert next(c for c in document["components"] if c["ref"] == "U1")["mean_c"] is None


def test_a_failing_part_outweighs_a_missing_one() -> None:
    profile, components = inspection.plan_from_dict(plan())
    frame = frame_with({J1: 20.0, U1: 70.0, HS1: 40.0})
    frame[12:17, 16:21] = np.nan
    assert inspection.inspect(frame, components, profile, W, H).overall == inspection.FAIL


@pytest.mark.parametrize("bad, text", [
    ({"schema": 2}, "schema"),
    ({"unknown": 1}, "unknown key"),
    ({"profile": 3}, "profile must be an object"),
    ({"components": [{"ref": "X", "kind": "nothing", "roi": [0, 0, 5, 5]}]}, "has no rule"),
    ({"components": [{"ref": "X", "kind": "ic", "roi": [0, 0, 5]}]}, "roi must be"),
    ({"components": [{"ref": "X", "kind": "ic", "roi": [5, 5, 1, 1]}]}, "X"),
    ({"components": [{"ref": "X", "kind": "ic", "roi": [0, 0, 5, 5]}, {"ref": "X", "kind": "ic", "roi": [0, 0, 5, 5]}]}, "twice"),
    ({"components": [{"kind": "ic", "roi": [0, 0, 5, 5]}]}, "needs a ref"),
])
def test_a_bad_plan_is_refused_with_a_reason(bad: dict, text: str) -> None:
    with pytest.raises(inspection.PlanError, match=text):
        inspection.plan_from_dict(plan(**bad))


def test_a_rule_with_a_bad_value_or_key_is_refused() -> None:
    for rule in ({"max_c": "hot"}, {"max_c": math.nan}, {"colour": 1}, {"tolerance_c": 0}):
        data = plan()
        data["profile"]["rules"]["ic"] = rule
        with pytest.raises(inspection.PlanError):
            inspection.plan_from_dict(data)


# ---- export -----------------------------------------------------------------------------------------------------------------
def make_report() -> inspection.Report:
    profile, components = inspection.plan_from_dict(plan())
    frame = frame_with({J1: 60.0, U1: 70.0, HS1: 40.0})
    frame[19:24, 27:32] = np.nan
    return inspection.inspect(frame, components, profile, W, H)


def test_samples_follow_the_datalake_ingest_shape() -> None:
    samples = export.samples_from_report(make_report(), 1_735_689_600_000, "line-1", "fallback")
    names = {s["sourceId"] for s in samples}
    assert names == {"line-1/reflow"}                     # HS1 has no data and no task: it is left out
    sample = samples[0]
    assert sample["kind"] == export.KIND and sample["timestamp"] == 1_735_689_600_000
    assert set(sample["fields"]) == {f"{ref}.{stat}" for ref in ("J1", "U1") for stat in export.STATS}
    assert sample["fields"]["J1.mean_c"] == pytest.approx(60.0)
    assert all(isinstance(v, float) for v in sample["fields"].values())


def test_a_component_without_a_task_uses_the_run_name() -> None:
    profile, components = inspection.plan_from_dict(plan())
    report = inspection.inspect(frame_with({J1: 60.0, U1: 70.0, HS1: 40.0}), components, profile, W, H)
    names = {s["sourceId"] for s in export.samples_from_report(report, 1_735_689_600_000, "line-1", "night shift")}
    assert names == {"line-1/reflow", "line-1/night shift"}


@pytest.mark.parametrize("stamp", [1_700_000_000, True, 12.5, 0])
def test_a_timestamp_in_seconds_or_not_an_integer_is_refused(stamp) -> None:
    with pytest.raises(export.ExportError):
        export.samples_from_report(make_report(), stamp)


def test_jsonl_and_opcua_nodes() -> None:
    samples = export.samples_from_report(make_report(), 1_735_689_600_000, "line-1")
    lines = export.to_jsonl(samples).splitlines()
    assert len(lines) == len(samples) and json.loads(lines[0])["kind"] == export.KIND
    nodes = export.opcua_nodes(samples)
    assert "URTC/Vision/reflow/J1/mean_c" in nodes
    node = nodes["URTC/Vision/reflow/J1/mean_c"]
    assert node["type"] == "Double" and node["source_time"] == datetime.fromtimestamp(1_735_689_600, tz=timezone.utc).isoformat()


def test_the_token_is_never_needed_to_be_printed_and_a_missing_one_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("UVIS_TEST_TOKEN", raising=False)
    with pytest.raises(export.ExportError, match="holds no token"):
        export.post_samples("http://127.0.0.1:1", [{"sourceId": "a", "kind": "k", "timestamp": 1, "fields": {}}], "UVIS_TEST_TOKEN")
    monkeypatch.setenv("UVIS_TEST_TOKEN", "secret-value")
    with pytest.raises(export.ExportError) as caught:
        export.post_samples("ftp://x", [], "UVIS_TEST_TOKEN")
    assert "secret-value" not in str(caught.value)
    with pytest.raises(export.ExportError) as caught:
        export.post_samples("http://127.0.0.1:1", [{"sourceId": "a", "kind": "k", "timestamp": 1, "fields": {}}], "UVIS_TEST_TOKEN", timeout_s=1)
    assert "secret-value" not in str(caught.value)


def test_posting_to_a_local_server_sends_the_bearer_token_and_the_body(monkeypatch: pytest.MonkeyPatch) -> None:
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    seen: list[tuple[str, str, dict]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            seen.append((self.path, self.headers.get("Authorization", ""), body))
            self.send_response(200)
            self.end_headers()

        def log_message(self, *args) -> None:  # noqa: D102
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        monkeypatch.setenv("UVIS_TEST_TOKEN", "abc")
        samples = export.samples_from_report(make_report(), 1_735_689_600_000, "line-1")
        accepted = export.post_samples(f"http://127.0.0.1:{server.server_address[1]}", samples, "UVIS_TEST_TOKEN")
    finally:
        server.shutdown()
    assert accepted == len(samples) == len(seen)
    assert seen[0][0] == "/ingest" and seen[0][1] == "Bearer abc" and seen[0][2]["kind"] == export.KIND


# ---- the sensor ----------------------------------------------------------------------------------------------------
def test_a_stable_sensor_is_ok() -> None:
    base = sensor_drift.make_baseline(sensor_drift.synthetic_reference(32, 24, 8, seed=1))
    report = sensor_drift.compare(base, sensor_drift.synthetic_reference(32, 24, 8, seed=2))
    assert report.verdict == sensor_drift.OK and abs(report.offset_shift_c) < 0.2


def test_a_common_offset_is_drift_and_the_suggested_calibration_removes_it() -> None:
    base = sensor_drift.make_baseline(sensor_drift.synthetic_reference(32, 24, 8, seed=1))
    later = sensor_drift.synthetic_reference(32, 24, 8, seed=2, offset_c=1.5)
    report = sensor_drift.compare(base, later)
    assert report.verdict == sensor_drift.DRIFT and report.offset_shift_c == pytest.approx(1.5, abs=0.15)
    from vision_companion.calibration import calibration_from_dict
    calibration = calibration_from_dict(sensor_drift.suggest_calibration(base, later))
    corrected = np.stack([calibration.apply(frame) for frame in later])
    assert sensor_drift.compare(base, corrected).verdict == sensor_drift.OK


def test_dead_pixels_are_found_and_reported_as_new() -> None:
    base = sensor_drift.make_baseline(sensor_drift.synthetic_reference(32, 24, 8, seed=1))
    assert base.dead_pixels == ()
    later = sensor_drift.synthetic_reference(32, 24, 8, seed=2, dead=((3, 4), (30, 20)))
    report = sensor_drift.compare(base, later)
    assert report.verdict == sensor_drift.DEAD and report.new_dead_pixels == ((3, 4), (30, 20))
    again = sensor_drift.make_baseline(later)
    assert again.dead_pixels == ((3, 4), (30, 20))
    assert sensor_drift.compare(again, sensor_drift.synthetic_reference(32, 24, 8, seed=3, dead=((3, 4), (30, 20)))).verdict == sensor_drift.OK
    recovered = sensor_drift.compare(again, sensor_drift.synthetic_reference(32, 24, 8, seed=3))
    assert recovered.recovered_pixels == ((3, 4), (30, 20))


def test_a_stuck_pixel_and_a_pixel_far_from_the_wall_level_are_dead() -> None:
    stack = sensor_drift.synthetic_reference(32, 24, 8, seed=1)
    stack[:, 5, 5] = 24.0          # no noise at all
    stack[:, 10, 10] += 8.0        # reads 8 degrees warm on a uniform wall
    assert set(sensor_drift.find_dead_pixels(stack)) == {(5, 5), (10, 10)}


def test_a_noisy_pixel_is_dead() -> None:
    stack = sensor_drift.synthetic_reference(32, 24, 8, seed=1)
    stack[::2, 7, 7] += 6.0
    assert (7, 7) in sensor_drift.find_dead_pixels(stack)


def test_too_few_frames_and_a_baseline_of_another_size_are_refused() -> None:
    with pytest.raises(sensor_drift.DriftError, match="at least"):
        sensor_drift.make_baseline(sensor_drift.synthetic_reference(32, 24, 2))
    base = sensor_drift.make_baseline(sensor_drift.synthetic_reference(32, 24, 8))
    with pytest.raises(sensor_drift.DriftError, match="baseline is"):
        sensor_drift.compare(base, sensor_drift.synthetic_reference(16, 12, 8))


def test_the_baseline_survives_a_file(tmp_path: Path) -> None:
    base = sensor_drift.make_baseline(sensor_drift.synthetic_reference(32, 24, 8, dead=((1, 1),)))
    path = tmp_path / "b.json"
    path.write_text(json.dumps(base.to_dict()), encoding="utf-8")
    loaded = sensor_drift.load_baseline(path)
    assert loaded.dead_pixels == ((1, 1),) and loaded.mean_c.shape == (24, 32)
    assert np.allclose(loaded.mean_c, base.mean_c, equal_nan=True, atol=1e-3)
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(sensor_drift.DriftError):
        sensor_drift.load_baseline(path)


# ---- the commands ------------------------------------------------------------------------------------------------------
def test_inspect_command_end_to_end(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan()), encoding="utf-8")
    frame_path = tmp_path / "f.npy"
    np.save(frame_path, frame_with({J1: 40.0, U1: 70.0, HS1: 40.0}))
    out = tmp_path / "report.json"
    jsonl = tmp_path / "s.jsonl"
    opcua = tmp_path / "n.json"
    code = cli.main(["inspect", str(plan_path), "--frame", str(frame_path), "--out", str(out), "--export-jsonl", str(jsonl),
                     "--opcua-nodes", str(opcua), "--timestamp-ms", "1735689600000", "--source-id", "line-1"])
    assert code == cli.EXIT_FINDINGS
    assert json.loads(out.read_text(encoding="utf-8"))["overall"] == "fail"
    assert {json.loads(line)["sourceId"] for line in jsonl.read_text(encoding="utf-8").splitlines()} == {"line-1/reflow", "line-1/default"}
    assert "URTC/Vision/reflow/J1/mean_c" in json.loads(opcua.read_text(encoding="utf-8"))
    assert "J1 (joint): cold" in capsys.readouterr().out


def test_inspect_command_passes_and_refuses_a_bad_plan(tmp_path: Path) -> None:
    good = tmp_path / "plan.json"
    good.write_text(json.dumps(plan()), encoding="utf-8")
    frame_path = tmp_path / "f.npy"
    np.save(frame_path, frame_with({J1: 60.0, U1: 70.0, HS1: 40.0}))
    assert cli.main(["inspect", str(good), "--frame", str(frame_path)]) == cli.EXIT_OK
    bad = tmp_path / "bad.json"
    bad.write_text("{}", encoding="utf-8")
    assert cli.main(["inspect", str(bad)]) == cli.EXIT_BAD_INPUT
    assert cli.main(["inspect", str(tmp_path / "missing.json")]) == cli.EXIT_BAD_INPUT


def test_drift_check_command(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    baseline = tmp_path / "b.json"
    frames = tmp_path / "frames.npy"
    np.save(frames, sensor_drift.synthetic_reference(32, 24, 6, seed=1))
    assert cli.main(["drift-check", str(baseline), "--frames", str(frames), "--update"]) == cli.EXIT_OK
    assert cli.main(["drift-check", str(baseline), "--frames", str(frames)]) == cli.EXIT_OK
    np.save(frames, sensor_drift.synthetic_reference(32, 24, 6, seed=2, offset_c=2.0, dead=((2, 2),)))
    suggested = tmp_path / "cal.json"
    assert cli.main(["drift-check", str(baseline), "--frames", str(frames), "--suggest-calibration", str(suggested)]) == cli.EXIT_FINDINGS
    out = capsys.readouterr().out
    assert "drift_and_dead_pixels" in out and "(2,2)" in out
    assert cli.main(["selftest", "--out", str(tmp_path / "o"), "--calibration", str(suggested)]) in (cli.EXIT_OK, cli.EXIT_BAD_INPUT)
    assert cli.main(["drift-check", str(tmp_path / "none.json")]) == cli.EXIT_BAD_INPUT
