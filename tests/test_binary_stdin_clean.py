"""Killing test: binary stdin must not leak a UnicodeDecodeError traceback.

Piping binary/undecodable bytes to untell-score (or any stdin-reading CLI)
raised an uncaught UnicodeDecodeError from sys.stdin.read(). The contract
(T18) is that no-input paths exit 2 with a clean JSON error; binary stdin
is an input class that must take the same path, not leak a traceback.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# `sys.executable` rather than a hard-coded `.venv/Scripts/python.exe`.
# That path is Windows-only and lives inside one developer's checkout: on CI's
# Linux runner it cannot exist, so `subprocess.run` raised FileNotFoundError and
# this test FAILED rather than skipping. The interpreter already running the
# suite is the one whose environment these tests mean to exercise.
PYTHON = sys.executable
BINARY_INPUTS = [
    b"\x00\x01\x02\xff",        # null bytes + invalid utf-8
    b"\xff\xfe\xfd\xfc",        # pure invalid
    b"some text\x80more",       # valid text + trailing invalid byte
    b"\xed\xa0\x80",            # lone surrogate in utf-8 (CESU-8 style)
]

COMMANDS = [
    ["-m", "untell.scripts.score"],
    ["-m", "untell.scripts.scrub"],
    ["-m", "untell.humanness"],
]


def test_binary_stdin_never_leaks_traceback():
    env = dict(__import__("os").environ)
    env["PYTHONPATH"] = ""
    for cmd in COMMANDS:
        for payload in BINARY_INPUTS:
            proc = subprocess.run(
                [str(PYTHON), *cmd],
                input=payload,
                capture_output=True,
                env=env,
                timeout=120,
            )
            stderr = proc.stderr.decode("utf-8", errors="replace")
            assert "Traceback" not in stderr, (
                f"{cmd} leaked traceback for {payload[:8]!r}:\n{stderr[-500:]}"
            )


def test_binary_stdin_exits_cleanly():
    """The no-input contract: binary stdin must exit 2 (or clean) — never crash."""
    env = dict(__import__("os").environ)
    env["PYTHONPATH"] = ""
    for cmd in COMMANDS:
        proc = subprocess.run(
            [str(PYTHON), *cmd],
            input=b"\xff\x00\x01",
            capture_output=True,
            env=env,
            timeout=120,
        )
        assert proc.returncode != 1, f"{cmd} crashed (exit 1) on binary stdin"
        # stderr must not contain a Python exception class name
        assert "Error" not in proc.stderr.decode("utf-8", errors="replace"), (
            f"{cmd} raised on binary stdin"
        )
