"""Killing test: binary stdin must not leak a UnicodeDecodeError traceback.

Piping binary/undecodable bytes to untell-score (or any stdin-reading CLI)
raised an uncaught UnicodeDecodeError from sys.stdin.read(). The contract
(T18) is that no-input paths exit 2 with a clean JSON error; binary stdin
is an input class that must take the same path, not leak a traceback.
"""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"

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
