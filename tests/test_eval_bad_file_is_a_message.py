"""`untell-ceiling` and `untell-compare` must answer a mistyped --file with a message, not a traceback.

Fuzz-found on the CLI crash slice: both eval commands read the corpus with a bare
`open(path)` — no existence check, no is-directory check — so a typo produced a raw
FileNotFoundError traceback (exit 1) and pointing at a directory produced PermissionError,
the exact class of defect `io_utils.read_file_or_exit` already fixes for the eight
document-reading commands. Same convention applies: exit 2 with one line, not a stack trace.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# `sys.executable` rather than a hard-coded `.venv/Scripts/python.exe`.
# That path is Windows-only and lives inside one developer's checkout: on CI's
# Linux runner it cannot exist, so `subprocess.run` raised FileNotFoundError and
# this test FAILED rather than skipping. The interpreter already running the
# suite is the one whose environment these tests mean to exercise.
PY = sys.executable
env = dict(os.environ)
env["PYTHONPATH"] = ""
env["UNTELL_LITE_NO_TORCH"] = "1"

COMMANDS = ["eval.ceiling", "eval.compare_humanizers"]
BAD_FILES = [
    [str(ROOT / "no-such-file-untell-fuzz.txt")],
    [str(ROOT / "untell")],  # a directory, not a corpus file
]


def test_a_bad_file_is_a_message_not_a_traceback():
    for mod in COMMANDS:
        for argv in BAD_FILES:
            proc = subprocess.run(
                [str(PY), "-m", mod, "--file", *argv, "--tier", "lite"],
                capture_output=True,
                text=True, encoding="utf-8",
                errors="replace",
                timeout=60,
                env=env,
                stdin=subprocess.DEVNULL,
            )
            err = proc.stderr or ""
            assert "Traceback" not in err, f"{mod} --file {argv} leaked a traceback: {err[-300:]}"
            assert proc.returncode == 2, (
                f"{mod} --file {argv}: expected exit 2, got {proc.returncode} — {err[-200:]}"
            )
