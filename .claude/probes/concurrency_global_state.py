"""Probe 6: global-state pollution from importing untell.mcp_server / api_server.

Q1: does importing the servers move the process RNG or change subsequent scoring?
Q2: does importing them mutate the module-level caches (untell.scripts.quality
    _model/_bs_model) or detector class-level caches at import time?
Q3: does a prior rewrite in the same process (which populates the quality.py
    model cache) change a subsequent score_text result vs a pristine process?

Each question answered in a FRESH subprocess, comparing against a control
subprocess that never touches the server modules.

Run:  PYTHONPATH= UNTELL_LITE_NO_TORCH=1 .venv/Scripts/python.exe .claude/probes/concurrency_global_state.py
"""
from __future__ import annotations

import json
import os
import pickle
import random
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PY = REPO / ".venv" / "Scripts" / "python.exe"

TEXT = (
    "The advancement of artificial intelligence has revolutionized the way we approach "
    "complex problems across many domains. Researchers continue to develop increasingly "
    "sophisticated models that demonstrate remarkable capabilities."
)

FINDINGS: list[str] = []


def env() -> dict:
    e = dict(os.environ)
    e["PYTHONPATH"] = ""
    e["UNTELL_LITE_NO_TORCH"] = "1"
    return e


CONTROL = r"""
import json, pickle, random, sys
from untell.scripts.score import score_text
text = json.loads(sys.argv[1])
rng_before = pickle.dumps(random.getstate())
r1 = score_text(text, tier="lite")
rng_after = pickle.dumps(random.getstate())
import untell.scripts.quality as q
cache_before = q._model is q._UNSET
print(json.dumps({"rng_moved": rng_before != rng_after,
                  "score": r1, "quality_cache_pristine": cache_before}))
"""

IMPORT_SERVERS = r"""
import json, pickle, random, sys
from untell.scripts.score import score_text
text = json.loads(sys.argv[1])
rng_before = pickle.dumps(random.getstate())
import untell.mcp_server   # noqa: F401
import untell.api_server   # noqa: F401
rng_after = pickle.dumps(random.getstate())
r1 = score_text(text, tier="lite")
import untell.scripts.quality as q
cache_before = q._model is q._UNSET
# also: is a NEW RNG seeded at import? compare a second scoring run too
r2 = score_text(text, tier="lite")
print(json.dumps({"rng_moved_by_import": rng_before != rng_after,
                  "score": r1, "score2": r2,
                  "quality_cache_pristine": cache_before,
                  "same_r1_r2": r1 == r2}))
"""

REWRITE_THEN_SCORE = r"""
import json, sys
from untell.scripts.score import score_text
from untell.scripts.run import untell_text
text = json.loads(sys.argv[1])
untell_text(text, tier="lite", rewriter="surgical", max_iters=1, best_of=1, seed=42)
r = score_text(text, tier="lite")
import untell.scripts.quality as q
print(json.dumps({"score_after_rewrite": r,
                  "quality_cache_populated": q._model is not q._UNSET}))
"""


def run_child(code: str, label: str) -> dict:
    p = subprocess.run(
        [str(PY), "-c", code, json.dumps(TEXT)],
        capture_output=True, text=True, env=env(), timeout=300,
    )
    if p.returncode != 0:
        FINDINGS.append(f"{label}: subprocess failed rc={p.returncode} stderr={p.stderr[:300]!r}")
        return {}
    return json.loads(p.stdout.strip().splitlines()[-1])


def main() -> int:
    t0 = time.time()
    control = run_child(CONTROL, "control")
    imported = run_child(IMPORT_SERVERS, "import-servers")
    rewrote = run_child(REWRITE_THEN_SCORE, "rewrite-then-score")
    print(f"[pollution] 3 subprocesses finished in {time.time()-t0:.1f}s")

    if not control or not imported:
        print("\n=== FINDINGS ===")
        for i, f in enumerate(FINDINGS, 1):
            print(f"{i}. {f}")
        return 1

    # Q1: RNG moved by importing servers?
    if imported.get("rng_moved_by_import"):
        FINDINGS.append(
            "GLOBAL-STATE LEAK: importing untell.mcp_server/api_server MOVES the "
            "process RNG (random.getstate() differs before/after import)"
        )
    print(f"[pollution] RNG moved by importing servers: {imported.get('rng_moved_by_import')}")

    # Q1b: does importing servers change scoring? (control vs imported)
    if control.get("score") != imported.get("score"):
        FINDINGS.append(
            "GLOBAL-STATE LEAK: importing mcp_server/api_server CHANGES subsequent "
            "score_text results "
            f"(control={json.dumps(control['score'], sort_keys=True)[:120]} "
            f"imported={json.dumps(imported['score'], sort_keys=True)[:120]})"
        )
    print(f"[pollution] score unchanged by server imports: {control.get('score') == imported.get('score')}")

    # Q2: quality.py caches pristine after import?
    if not imported.get("quality_cache_pristine"):
        FINDINGS.append(
            "GLOBAL-STATE LEAK: importing mcp_server/api_server POPULATES the "
            "untell.scripts.quality model cache (module-level _model no longer _UNSET)"
        )
    print(f"[pollution] quality cache pristine after imports: {imported.get('quality_cache_pristine')}")

    # Q3: rewrite-then-score in same process vs control
    if rewrote and rewrote.get("score_after_rewrite") != control.get("score"):
        FINDINGS.append(
            "GLOBAL-STATE LEAK: running untell_text first CHANGES subsequent score_text "
            "results for the same text "
            f"(control={json.dumps(control['score'], sort_keys=True)[:120]} "
            f"after-rewrite={json.dumps(rewrote['score_after_rewrite'], sort_keys=True)[:120]})"
        )
    print(f"[pollution] score unchanged after a prior rewrite: {not rewrote or rewrote.get('score_after_rewrite') == control.get('score')}")

    if rewrote and rewrote.get("quality_cache_populated"):
        print("[pollution] note: quality._model cache IS populated by the rewrite path (expected lazy load)")

    print("\n=== FINDINGS ===")
    if not FINDINGS:
        print("none — importing the servers is side-effect free for RNG/scoring/caches")
    for i, f in enumerate(FINDINGS, 1):
        print(f"{i}. {f}")
    return 1 if FINDINGS else 0


if __name__ == "__main__":
    sys.exit(main())
