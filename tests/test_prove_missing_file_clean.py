"""Killing test: untell-prove missing file must exit 2 naming the file, not traceback.

eval/prove.py opened args.file with a raw open() -> FileNotFoundError
traceback leaked on a missing file. Every other CLI uses read_file_or_exit
(exit 2, one line naming the file — the T18 contract).
"""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = ROOT / ".venv" / "Scripts" / "python.exe"

env = dict(__import__("os").environ)
env["PYTHONPATH"] = ""
env["UNTELL_LITE_NO_TORCH"] = "1"


def test_prove_missing_file_no_traceback():
    proc = subprocess.run(
        [str(PY), "-m", "eval.prove", "--file", "nope_missing_xyz.txt"],
        capture_output=True,
        text=True, encoding="utf-8",
        errors="replace",
        timeout=120,
        env=env,
        stdin=subprocess.DEVNULL,
    )
    stderr = proc.stderr or ""
    assert "Traceback" not in stderr, f"traceback leaked:\n{stderr[-500:]}"
    assert "nope_missing_xyz" in stderr or "nope_missing_xyz" in (proc.stdout or ""), (
        "missing file not named in the error"
    )
