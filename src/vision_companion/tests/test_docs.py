"""docs/CLI_REFERENCE.md must describe the CLI that exists: its version, every
command, every option and the exit codes. (The help texts themselves are not
compared character by character - argparse lays them out differently between
Python versions.)"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

from vision_companion import __version__, cli

DOC = Path(__file__).resolve().parents[3] / "docs" / "CLI_REFERENCE.md"


def _doc() -> str:
    return DOC.read_text(encoding="utf-8")


def _all_parsers(parser: argparse.ArgumentParser):
    yield parser
    for action in parser._actions:  # noqa: SLF001 - argparse has no public way to list subparsers
        if isinstance(action, argparse._SubParsersAction):  # noqa: SLF001
            for sub in action.choices.values():
                yield from _all_parsers(sub)


def test_the_reference_names_the_current_version() -> None:
    text = _doc()
    assert f"vision-companion v{__version__} (URTC-VISION-TOOL)" in text
    assert f"vision-companion selftest v{__version__}" in text
    stale = set(re.findall(r"vision-companion(?: selftest)? v(\d+\.\d+\.\d+)", text)) - {__version__}
    assert not stale, f"the reference shows an old version: {stale}"


def test_the_reference_covers_every_command_and_option() -> None:
    text = _doc()
    for parser in _all_parsers(cli.build_parser()):
        for action in parser._actions:  # noqa: SLF001
            for flag in action.option_strings:
                assert flag in text, f"option {flag} is not documented"
            if isinstance(action, argparse._SubParsersAction):  # noqa: SLF001
                for name in action.choices:
                    assert f"### `{name}" in text, f"command {name} has no section"


def test_the_reference_lists_the_exit_codes_of_the_code() -> None:
    text = _doc()
    for code in (cli.EXIT_OK, cli.EXIT_NO_DATA, cli.EXIT_BAD_INPUT):
        assert f"| `{code}` |" in text, f"exit code {code} is not in the table"
    assert "Traceback" not in text, "the CLI no longer ends in a traceback; the reference must not show one"


def test_the_reference_points_at_the_files_that_exist() -> None:
    text = _doc()
    for relative in re.findall(r"`(src/vision_companion/[\w/.\-]+)`", text):
        assert (DOC.parents[1] / relative).exists(), f"{relative} does not exist"
