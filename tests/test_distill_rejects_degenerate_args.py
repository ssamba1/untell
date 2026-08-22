"""`untell-distill` must refuse degenerate numeric args at parse time, not silently run with them.

Fuzz-found on the CLI crash slice: --threshold is a bare `type=float`, so `--threshold nan`
parsed, and the distillation ran for minutes with a gate no probability can satisfy —
silently generating a biased training set from a nonsense configuration. Same refusal every
other CLI in this repo ships (cf. test_ceiling_rejects_bad_args.py): exit 2 at parse.
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

BAD_ARGS = [
    ["--threshold", "nan"],
    ["--threshold", "inf"],
    ["--threshold", "-0.5"],
    ["--threshold", "2.5"],
    ["--margin", "nan"],
    ["--margin", "-1"],
    ["--margin", "5"],
    ["--n", "0"],
    ["--n", "-3"],
    ["--best-of", "0"],
    ["--best-of", "-2"],
]


def test_distill_rejects_degenerate_args_fast():
    for argv in BAD_ARGS:
        proc = subprocess.run(
            [str(PY), "-m", "training.distill", *argv, "--tier", "lite"],
            capture_output=True,
            text=True, encoding="utf-8",
            errors="replace",
            timeout=30,  # a refusal must be instant; the old behaviour ran for minutes
            env=env,
            stdin=subprocess.DEVNULL,
        )
        err = proc.stderr or ""
        assert "Traceback" not in err, f"{argv} leaked a traceback: {err[-300:]}"
        assert proc.returncode == 2, f"{argv} expected exit 2, got {proc.returncode} — {err[-200:]}"


def test_distill_still_accepts_valid_defaults():
    """The checks must not refuse the documented defaults (parse-only path, no training)."""
    proc = subprocess.run(
        [str(PY), "-m", "training.distill", "--help"],
        capture_output=True,
        text=True, encoding="utf-8",
        errors="replace",
        timeout=30,
        env=env,
        stdin=subprocess.DEVNULL,
    )
    assert proc.returncode == 0
    assert "--threshold" in proc.stdout
