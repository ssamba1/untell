"""NOVEL probe: untell-loop CLI contract (the loop command, never directly probed).

Check: help, valid run, no-input, missing file, bad tier, bad seed, bad
threshold, --json shape, and exit codes. The loop is the product's core
promise — its CLI contract should match score/tells.
"""
import subprocess, sys, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PY = ROOT / ".venv" / "Scripts" / "python.exe"
MOD = "untell.scripts.run"

CASES = [
    ([], "no input"),
    (["--help"], "help"),
    (["--tier", "bogus", "hello"], "bad tier"),
    (["--seed", "-5", "text"], "negative seed"),
    (["--threshold", "abc", "text"], "bad threshold"),
    (["--threshold", "2.5", "text"], "out-of-range threshold"),
    (["--file", "nope.txt"], "missing file"),
    (["--tier", "lite", "--json", "--max-iters", "1", "the committee approved the proposal yesterday"],
     "valid lite json run"),
]

env = dict(__import__("os").environ)
env["PYTHONPATH"] = ""
env["UNTELL_LITE_NO_TORCH"] = "1"

for argv, desc in CASES:
    try:
        proc = subprocess.run([str(PY), "-m", MOD, *argv], capture_output=True,
                              text=True, errors="replace", timeout=120, env=env,
                              stdin=subprocess.DEVNULL)
        out = (proc.stdout or "").strip().replace("\n", " ")[:90]
        tb = "Traceback" in (proc.stderr or "")
        print(f"{desc:28} exit={proc.returncode} tb={tb} out={out}")
    except subprocess.TimeoutExpired:
        print(f"{desc:28} HANG (>120s)")
