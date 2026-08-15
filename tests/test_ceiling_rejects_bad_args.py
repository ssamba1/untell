"""Killing test: untell-ceiling must reject out-of-range numeric args.

Measured: --n 0 silently ran the default 3-sample builtin (exit 0, n=3),
--threshold 2.5 ran with a threshold where nothing can ever flag
(pre_flagged_rate 0.0), --repeats 0/-1 and --best-of 0 all silently ran.
Every other CLI (untell/score/loop/verify) rejects these at parse with
exit 2 — the measurements engine must too, or a quoted number can be
produced from a degenerate configuration.
"""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = ROOT / ".venv" / "Scripts" / "python.exe"

env = dict(__import__("os").environ)
env["PYTHONPATH"] = ""
env["UNTELL_LITE_NO_TORCH"] = "1"

BAD_ARGS = [
    ["--n", "0"],
    ["--n", "-1"],
    ["--repeats", "0"],
    ["--repeats", "-1"],
    ["--best-of", "0"],
    ["--best-of", "-1"],
    ["--threshold", "2.5"],
    ["--threshold", "-1"],
    ["--max-iters", "0"],
    ["--max-iters", "-1"],
    ["--workers", "0"],
    ["--workers", "-1"],
]


def test_ceiling_rejects_out_of_range_args():
    for argv in BAD_ARGS:
        proc = subprocess.run(
            [str(PY), "-m", "eval.ceiling", *argv, "--tier", "lite"],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=60,
            env=env,
            stdin=subprocess.DEVNULL,
        )
        assert "Traceback" not in (proc.stderr or ""), f"{argv} leaked traceback"
        assert proc.returncode == 2, (
            f"{argv} expected exit 2 (argparse range rejection), got {proc.returncode} — "
            f"it silently ran a measurement"
        )
