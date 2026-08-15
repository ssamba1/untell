"""NOVEL probe: untell-ceiling CLI argument boundaries.

The ceiling command is the measurements engine. Test its arg validation:
--repeats 0/-1/abc, --n 0/-1/abc, --workers 0/-1/abc, --threshold out of
range, --best-of 0, and the exit codes for each. No tracebacks allowed.
"""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PY = ROOT / ".venv" / "Scripts" / "python.exe"
MOD = "eval.ceiling"

env = dict(__import__("os").environ)
env["PYTHONPATH"] = ""
env["UNTELL_LITE_NO_TORCH"] = "1"

CASES = [
    (["--repeats", "0", "--n", "1", "--tier", "lite"], "repeats 0"),
    (["--repeats", "-1", "--n", "1", "--tier", "lite"], "repeats -1"),
    (["--repeats", "abc"], "repeats abc"),
    (["--n", "0", "--tier", "lite"], "n 0"),
    (["--n", "-1", "--tier", "lite"], "n -1"),
    (["--n", "abc"], "n abc"),
    (["--workers", "0", "--n", "1", "--tier", "lite"], "workers 0"),
    (["--workers", "-1", "--n", "1", "--tier", "lite"], "workers -1"),
    (["--workers", "abc"], "workers abc"),
    (["--threshold", "2.5", "--n", "1", "--tier", "lite"], "threshold 2.5"),
    (["--best-of", "0", "--n", "1", "--tier", "lite"], "best-of 0"),
    (["--dataset", "nope"], "bad dataset"),
]

for argv, desc in CASES:
    try:
        proc = subprocess.run([str(PY), "-m", MOD, *argv], capture_output=True,
                              text=True, errors="replace", timeout=15, env=env,
                              stdin=subprocess.DEVNULL)
        tb = "Traceback" in (proc.stderr or "")
        out = (proc.stdout or "").strip().replace("\n", " ")[:60]
        print(f"{desc:16} exit={proc.returncode} tb={tb} {out}")
    except subprocess.TimeoutExpired:
        # a valid measurement started (slow but not a hang)
        print(f"{desc:16} RUNNING (>15s, likely valid)")
