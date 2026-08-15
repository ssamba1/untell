"""Killing tests for .claude/verify.py mutation survivors (2026-08-14 sweep).

  line 65   logic: != -> ==       failing `git show` must refuse (exit != 0).
  line 68   logic: == -> !=       identical file must refuse.

Killed here via monkeypatched subprocess.run. Other survivors (33/39/40 x2/46/49/
50/61/76/90) are constants — annotated in survivors.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".claude"))
import verify as V  # noqa: E402


class _Result:
    def __init__(self, returncode, stdout=""):
        self.returncode = returncode
        self.stdout = stdout


class TestFailingGitShow:
    """Survivor verify.py:65 — `head.returncode != 0` -> `==`.

    When `git show HEAD:<file>` fails (returncode != 0), verify must REFUSE —
    there is no 'before' to revert to. The mutation proceeds past the guard."""

    def test_failing_git_show_refuses(self, monkeypatch) -> None:
        fix = Path("tests/test_verify_guard_placeholder.txt")
        fix.write_text("placeholder\n", encoding="utf-8")
        try:
            def _run(*a, **k):
                return _Result(1)  # git show failed

            monkeypatch.setattr(V.subprocess, "run", _run)
            monkeypatch.setattr(
                sys, "argv",
                ["verify", "--fix", str(fix), "tests/test_verify.py"],
            )
            with pytest.raises(SystemExit) as ei:
                V.main()
            assert "REFUSED" in str(ei.value)
        finally:
            fix.unlink(missing_ok=True)


class TestIdenticalFileRefuses:
    """Survivor verify.py:68 — `head.stdout == fixed` -> `!=`.

    When the working file is identical to HEAD, verify must REFUSE (no fix to
    take away). The mutation accepts it and proceeds to run tests."""

    def test_identical_file_refuses(self, monkeypatch) -> None:
        fix = Path("tests/test_verify_guard_placeholder.txt")
        content = "placeholder\n"
        fix.write_text(content, encoding="utf-8")
        try:
            def _run(*a, **k):
                return _Result(0, content)  # git show returns the SAME content

            monkeypatch.setattr(V.subprocess, "run", _run)
            monkeypatch.setattr(V, "run", lambda tests, timeout: (True, "ok"))
            monkeypatch.setattr(
                sys, "argv",
                ["verify", "--fix", str(fix), "tests/test_verify.py"],
            )
            with pytest.raises(SystemExit) as ei:
                V.main()
            assert "REFUSED" in str(ei.value)
        finally:
            fix.unlink(missing_ok=True)
