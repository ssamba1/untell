"""Probe 3: 4 parallel subprocess CLIs scoring the SAME text — JSON determinism.

Spawns 4 `python -m untell.scripts.score --tier lite` processes concurrently,
each reading the same input file, and byte-compares stdout (raw bytes AND parsed
JSON). Any difference across processes = process-level determinism break.

Run:  PYTHONPATH= UNTELL_LITE_NO_TORCH=1 .venv/Scripts/python.exe .claude/probes/concurrency_subprocess_cli.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PY = REPO / ".venv" / "Scripts" / "python.exe"
SAMPLE = REPO / ".claude" / "probes" / "_sample.txt"

TEXT = (
    "The advancement of artificial intelligence has revolutionized the way we approach "
    "complex problems across many domains. Researchers continue to develop increasingly "
    "sophisticated models that demonstrate remarkable capabilities in natural language "
    "understanding and generation. These systems have found practical applications in "
    "healthcare, education, and creative industries, and their influence continues to grow."
)

FINDINGS: list[str] = []


def env() -> dict:
    e = dict(os.environ)
    e["PYTHONPATH"] = ""
    e["UNTELL_LITE_NO_TORCH"] = "1"
    return e


def main() -> int:
    SAMPLE.write_text(TEXT, encoding="utf-8")
    cmd = [str(PY), "-m", "untell.scripts.score", "--file", str(SAMPLE), "--tier", "lite", "--quiet"]

    t0 = time.time()
    procs = [subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env()) for _ in range(4)]
    outs: list[tuple[int, bytes, bytes]] = []
    for p in procs:
        out, err = p.communicate(timeout=180)
        outs.append((p.returncode, out, err))
    wall = time.time() - t0
    print(f"[subprocess] 4 CLIs finished in {wall:.1f}s")

    codes = {rc for rc, _, _ in outs}
    if codes != {0}:
        FINDINGS.append(f"CLI exit codes not all 0: {codes} (stderr: {outs[0][2][:200]!r})")

    raw = [out for _, out, _ in outs]
    if len({hash(b) for b in raw}) != 1:
        FINDINGS.append(
            f"DETERMINISM BREAK (process-level): 4 parallel CLIs scored the same text "
            f"and stdout bytes differ. byte-lens={[len(b) for b in raw]}, "
            f"sha256s={[__import__('hashlib').sha256(b).hexdigest()[:12] for b in raw]}"
        )
        for i, b in enumerate(raw):
            print(f"  proc{i}: {b[:120]!r}")
    else:
        print(f"[subprocess] all 4 stdout byte-identical ({len(raw[0])} bytes, sha256 "
              f"{__import__('hashlib').sha256(raw[0]).hexdigest()[:12]})")

    # Also verify the parsed JSON matches and scores are present
    try:
        parsed = [json.loads(b) for b in raw]
        keysets = {tuple(sorted(p.keys())) for p in parsed}
        if len(keysets) != 1:
            FINDINGS.append(f"parsed JSON key sets differ across processes: {keysets}")
        scores = {p["detectors"]["perplexity_burstiness"] for p in parsed}
        if len(scores) != 1:
            FINDINGS.append(f"perplexity_burstiness score differs across processes: {scores}")
        print(f"[subprocess] parsed JSON identical: {len(parsed) == 4 and len({str(p) for p in parsed}) == 1}")
    except Exception as e:  # noqa: BLE001
        FINDINGS.append(f"could not parse CLI JSON: {e!r}")

    print("\n=== FINDINGS ===")
    if not FINDINGS:
        print("none — CLI scoring is deterministic across processes")
    for i, f in enumerate(FINDINGS, 1):
        print(f"{i}. {f}")
    return 1 if FINDINGS else 0


if __name__ == "__main__":
    sys.exit(main())
