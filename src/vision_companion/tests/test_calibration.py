from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from vision_companion import cli
from vision_companion.calibration import (
    Calibration,
    CalibrationError,
    calibration_from_dict,
    load_calibration,
)


def _write(tmp_path: Path, data: object) -> Path:
    path = tmp_path / "cal.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_identity_calibration_leaves_the_frame_unchanged() -> None:
    frame = cli.generate_synthetic_thermal_frame()
    cal = calibration_from_dict({"schema": 1})
    assert cal.is_identity
    assert np.array_equal(cal.apply(frame), frame)


def test_gain_offset_and_pixel_offsets_are_applied_in_order() -> None:
    frame = np.full((2, 3), 10.0, dtype=np.float32)
    cal = calibration_from_dict({
        "schema": 1, "gain": 2.0, "offset_c": 1.0,
        "pixel_offsets_c": [[0, 1, 2], [3, 4, 5]],
    })
    assert cal.apply(frame).tolist() == [[21.0, 22.0, 23.0], [24.0, 25.0, 26.0]]


def test_apply_does_not_modify_its_input() -> None:
    frame = np.full((2, 2), 5.0, dtype=np.float32)
    calibration_from_dict({"schema": 1, "gain": 3.0, "dead_pixels": [[0, 0]]}).apply(frame)
    assert frame.tolist() == [[5.0, 5.0], [5.0, 5.0]]


def test_dead_pixels_become_nan_and_are_counted_as_invalid() -> None:
    frame = cli.generate_synthetic_thermal_frame()
    out = calibration_from_dict({"schema": 1, "dead_pixels": [[3, 4], [31, 23]]}).apply(frame)
    assert np.isnan(out[4, 3]) and np.isnan(out[23, 31])
    assert int(np.isnan(out).sum()) == 2


def test_a_map_of_the_wrong_size_is_refused() -> None:
    cal = calibration_from_dict({"schema": 1, "pixel_offsets_c": [[0, 0], [0, 0]]})
    with pytest.raises(CalibrationError, match="2x2"):
        cal.apply(cli.generate_synthetic_thermal_frame())


def test_a_dead_pixel_outside_the_frame_is_refused() -> None:
    cal = calibration_from_dict({"schema": 1, "dead_pixels": [[16, 0]]})
    with pytest.raises(CalibrationError, match="outside"):
        cal.apply(cli.generate_synthetic_thermal_frame(16, 12))


BAD_DATA = [
    [],
    {},
    {"schema": 2},
    {"schema": True},
    {"schema": 1, "gain": 0},
    {"schema": 1, "gain": -1.0},
    {"schema": 1, "gain": "1"},
    {"schema": 1, "gain": True},
    {"schema": 1, "offset_c": float("inf")},
    {"schema": 1, "gain_typo": 1.0},
    {"schema": 1, "pixel_offsets_c": []},
    {"schema": 1, "pixel_offsets_c": [[1, 2], [3]]},
    {"schema": 1, "pixel_offsets_c": [[1, "x"]]},
    {"schema": 1, "dead_pixels": [[1]]},
    {"schema": 1, "dead_pixels": [[-1, 0]]},
    {"schema": 1, "dead_pixels": [[1.5, 0]]},
    {"schema": 1, "dead_pixels": "none"},
]


def test_bad_calibration_data_is_refused() -> None:
    for data in BAD_DATA:
        with pytest.raises(CalibrationError):
            calibration_from_dict(data)


def test_load_reports_a_missing_file_and_bad_json(tmp_path: Path) -> None:
    with pytest.raises(CalibrationError, match="cannot read"):
        load_calibration(tmp_path / "missing.json")
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(CalibrationError, match="not valid JSON"):
        load_calibration(bad)


def test_calibration_class_rejects_a_zero_gain() -> None:
    with pytest.raises(CalibrationError):
        Calibration(gain=0.0)


def test_analyze_roi_uses_the_calibration(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["analyze-roi", "0", "0", "640", "480"]) == cli.EXIT_OK
    plain = capsys.readouterr().out
    path = _write(tmp_path, {"schema": 1, "offset_c": 10.0})
    assert cli.main(["analyze-roi", "0", "0", "640", "480", "--calibration", str(path)]) == cli.EXIT_OK
    shifted = capsys.readouterr().out
    assert plain != shifted
    assert "invalid thermal px" not in shifted

    path = _write(tmp_path, {"schema": 1, "dead_pixels": [[0, 0]]})
    assert cli.main(["analyze-roi", "0", "0", "640", "480", "--calibration", str(path)]) == cli.EXIT_OK
    assert "1 invalid thermal px" in capsys.readouterr().out


def test_cli_exits_2_on_an_unusable_calibration(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    missing = str(tmp_path / "missing.json")
    assert cli.main(["analyze-roi", "0", "0", "64", "48", "--calibration", missing]) == cli.EXIT_BAD_INPUT
    assert "error:" in capsys.readouterr().err
    assert cli.main(["selftest", "--out", str(tmp_path / "o"), "--calibration", missing]) == cli.EXIT_BAD_INPUT
    wrong = _write(tmp_path, {"schema": 1, "pixel_offsets_c": [[0.0]]})
    assert cli.main(["selftest", "--out", str(tmp_path / "o"), "--calibration", str(wrong)]) == cli.EXIT_BAD_INPUT
    assert "error:" in capsys.readouterr().err


def test_selftest_with_a_calibration_writes_the_corrected_frame(tmp_path: Path) -> None:
    path = _write(tmp_path, {"schema": 1, "offset_c": 5.0})
    out = tmp_path / "out"
    assert cli.main(["selftest", "--out", str(out), "--calibration", str(path)]) == cli.EXIT_OK
    saved = np.load(out / "thermal_frame.npy")
    assert np.allclose(saved, cli.generate_synthetic_thermal_frame() + 5.0, atol=1e-4)
