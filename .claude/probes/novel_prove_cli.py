"""NOVEL probe: untell-prove CLI contract (never directly probed).

The commercial-tier proof command. Check failure paths don't leak tracebacks
when commercial keys are absent (the realistic state for most users).
"""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PY = ROOT / ".venv" / "Scripts" / "python.exe"
MOD = "eval.prove"

env = dict(__import__("os").environ)
env["PYTHONPATH"] = ""
env["UNTELL_LITE_NO_TORCH"] = "1"

CASES = [
    ([], "no input"),
    (["--help"], "help"),
    (["--tier", "bogus", "text"], "bad tier"),
    (["--file", "nope.txt"], "missing file"),
    (["--max-iters", "0", "some text"], "zero iters"),
    (["--threshold", "abc", "text"], "bad threshold"),
    (["--json", "the committee approved the proposal yesterday"], "valid json run"),
]

for argv, desc in CASES:
    try:
        proc = subprocess.run([str(PY), "-m", MOD, *argv], capture_output=True,
                              text=True, errors="replace", timeout=180, env=env,
                              stdin=subprocess.DEVNULL)
        out = (proc.stdout or "").strip().replace("\n", " ")[:100]
        tb = "Traceback" in (proc.stderr or "")
        print(f"{desc:22} exit={proc.returncode} tb={tb} out={out}")
    except subprocess.TimeoutExpired:
        print(f"{desc:22} HANG (>180s)")
