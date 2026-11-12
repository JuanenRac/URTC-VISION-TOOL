"""The version of the Python vision_companion package has its own odometer step in bump.py (it is independent of the version of the project)."""
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("project_bump", ROOT / "bump.py")
assert _spec is not None and _spec.loader is not None
bump = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bump)


def init_file(folder: Path, line: str, newline: str = "\n") -> Path:
    path = folder / "__init__.py"
    path.write_bytes(('"""The package."""' + newline + newline + line + newline).encode("utf-8"))
    return path


class CompanionOdometerTests(unittest.TestCase):
    def test_the_patch_carries_into_the_minor_and_the_minor_into_the_major(self):
        self.assertEqual(bump.next_companion_version(0, 0, 3), (0, 0, 4))
        self.assertEqual(bump.next_companion_version(0, 0, 9), (0, 1, 0))
        self.assertEqual(bump.next_companion_version(0, 9, 9), (1, 0, 0))
        self.assertEqual(bump.next_companion_version(1, 10, 0), (2, 0, 1), "a minor already above 9 for any other reason still carries")

    def test_the_version_line_is_raised_and_nothing_else_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            path = init_file(Path(folder), '__version__ = "0.0.3"')
            self.assertEqual(bump.bump_companion(path), "0.0.4")
            self.assertEqual(path.read_text(encoding="utf-8"), '"""The package."""\n\n__version__ = "0.0.4"\n')

    def test_a_dry_run_writes_nothing_and_the_line_endings_are_kept(self):
        with tempfile.TemporaryDirectory() as folder:
            path = init_file(Path(folder), '__version__ = "0.0.9"', "\r\n")
            before = path.read_bytes()
            self.assertEqual(bump.bump_companion(path, dry_run=True), "0.1.0")
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(bump.bump_companion(path), "0.1.0")
            self.assertEqual(path.read_bytes(), before.replace(b"0.0.9", b"0.1.0"))
            self.assertNotIn(b"\n", path.read_bytes().replace(b"\r\n", b""))

    def test_a_file_without_exactly_one_version_line_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            for text in ('', '__version__ = "x"', '__version__ = "0.0.1"\n__version__ = "0.0.2"'):
                path = init_file(Path(folder), text)
                with self.assertRaises(SystemExit):
                    bump.bump_companion(path)

    def test_the_real_package_has_one_readable_version_line(self):
        self.assertRegex(bump.COMPANION_INIT.read_text(encoding="utf-8"), bump.COMPANION_LINE)
        done = subprocess.run([sys.executable, str(ROOT / "bump.py"), "--companion", "--dry-run"], capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertRegex(done.stdout.strip(), r"^\d+\.\d+\.\d+$")


if __name__ == "__main__":
    unittest.main()
