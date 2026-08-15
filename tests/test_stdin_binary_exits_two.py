"""NUL-bearing piped stdin must take the no-input exit-2 path, never be scored as prose.

The existing binary-stdin test forbids exit 1 (crashes) but allows exit 0. On codecs that
decode NUL bytes instead of raising (Windows cp1252/latin-1 pipes), a piped binary file
decoded as text and was scored and "humanized" as prose with exit 0 — MEASURED on this
host: `untell humanize` on piped b'\\x00\\x01\\x02\\xff' reported "humanization complete".
Real text contains no NUL at all (the same policy `_reject_if_binary` applies to files),
so the reader must refuse it: clean "no input" exit 2, per the documented contract.
"""

from __future__ import annotations

import io
import os
import subprocess
from pathlib import Path

from untell.scripts.io_utils import read_stdin_or_none

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"

NUL_PAYLOADS = [
    b"\x00\x01\x02\xff",
    b"hello\x00world",
    b"\x00" * 10,
]


def test_nul_text_is_refused_by_the_stdin_reader(monkeypatch):
    """Unit: a decoded string containing NUL must come back as None (the no-input signal)."""
    for payload in NUL_PAYLOADS:
        monkeypatch.setattr("sys.stdin", io.StringIO(payload.decode("latin-1")))
        assert read_stdin_or_none() is None, f"{payload!r} should be refused, not returned"


def test_nul_text_is_still_readable_without_nul(monkeypatch):
    """The guard must not reject ordinary text."""
    monkeypatch.setattr("sys.stdin", io.StringIO("hello world"))
    assert read_stdin_or_none() == "hello world"


def test_binary_stdin_exits_two_across_commands():
    """End to end: a NUL-bearing pipe exits 2 with the no-input error on every stdin CLI."""
    env = dict(os.environ)
    env["PYTHONPATH"] = ""
    env["UNTELL_LITE_NO_TORCH"] = "1"
    for cmd in (["-m", "untell.scripts.score"], ["-m", "untell.scripts.run"]):
        for payload in NUL_PAYLOADS:
            proc = subprocess.run(
                [str(PYTHON), *cmd, "--tier", "lite"],
                input=payload,
                capture_output=True,
                env=env,
                timeout=60,
            )
            err = proc.stderr.decode("utf-8", errors="replace")
            assert "Traceback" not in err
            assert proc.returncode == 2, (
                f"{cmd} on {payload[:8]!r}: expected exit 2 (no input), got {proc.returncode}"
            )
