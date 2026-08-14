"""Probe 5: seed reproducibility — same input + same seed=42 in FRESH processes.

For each of the structural / targeted rewriters, spawn 2 independent subprocesses
that rewrite the SAME text with seed=42 and print the result JSON. The `final`
texts (and full result dicts) must be byte-identical across processes.
All 4 subprocesses run concurrently to bound wall time (~60s one-time import each).

Run:  PYTHONPATH= UNTELL_LITE_NO_TORCH=1 .venv/Scripts/python.exe .claude/probes/concurrency_seed_repro.py
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PY = REPO / ".venv" / "Scripts" / "python.exe"

TEXT = (
    "The advancement of artificial intelligence has revolutionized the way we approach "
    "complex problems across many domains. Researchers continue to develop increasingly "
    "sophisticated models that demonstrate remarkable capabilities in natural language "
    "understanding and generation. These systems have found practical applications in "
    "healthcare, education, and creative industries."
)

FINDINGS: list[str] = []

CHILD = r"""
import json, sys
from untell.scripts.run import untell_text
TEXT = json.loads(sys.argv[1])
rewriter = sys.argv[2]
seed = int(sys.argv[3])
r = untell_text(TEXT, tier="lite", rewriter=rewriter, max_iters=1, best_of=1, seed=seed)
print(json.dumps({"final": r["final"], "flagged": r.get("flagged"),
                  "post": r.get("post"), "pre": r.get("pre"), "seed": r.get("seed")}))
"""


def env() -> dict:
    e = dict(os.environ)
    e["PYTHONPATH"] = ""
    e["UNTELL_LITE_NO_TORCH"] = "1"
    return e


def main() -> int:
    t0 = time.time()
    procs = []
    # 2 fresh processes per rewriter, all 4 concurrent
    for rewriter in ("structural", "targeted"):
        for _ in range(2):
            procs.append((
                rewriter,
                subprocess.Popen(
                    [str(PY), "-c", CHILD, json.dumps(TEXT), rewriter, "42"],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env(),
                ),
            ))

    results: dict[str, list[tuple[int, bytes, bytes]]] = {"structural": [], "targeted": []}
    for rewriter, p in procs:
        out, err = p.communicate(timeout=300)
        results[rewriter].append((p.returncode, out, err))
    print(f"[seed] 4 fresh subprocesses finished in {time.time()-t0:.1f}s")

    for rewriter, runs in results.items():
        codes = {rc for rc, _, _ in runs}
        finals = [json.loads(o)["final"] for rc, o, _ in runs if rc == 0 and o.strip()]
        full = [o for rc, o, _ in runs if rc == 0 and o.strip()]
        if codes != {0}:
            FINDINGS.append(
                f"subprocess failed for {rewriter}: codes={codes} "
                f"stderr={runs[0][2][:200]!r}"
            )
            continue
        if len(finals) != 2:
            FINDINGS.append(f"{rewriter}: expected 2 finals, got {len(finals)}")
            continue
        identical = finals[0] == finals[1] and full[0] == full[1]
        print(f"[seed] {rewriter}: finals byte-identical across 2 fresh processes: {identical}")
        if not identical:
            h = lambda b: hashlib.sha256(b).hexdigest()[:12]  # noqa: E731
            FINDINGS.append(
                f"DETERMINISM BREAK (process-level, seed=42, rewriter={rewriter}): "
                f"same input + same seed in two fresh processes produced DIFFERENT output. "
                f"final sha256={h(finals[0].encode())} vs {h(finals[1].encode())}, "
                f"len {len(finals[0])} vs {len(finals[1])}; "
                f"full-json identical={full[0] == full[1]}; "
                f"first diff: {next((i for i in range(min(len(finals[0]), len(finals[1]))) if finals[0][i] != finals[1][i]), 'len')}"
            )
            print(f"    proc A: {finals[0][:160]!r}")
            print(f"    proc B: {finals[1][:160]!r}")
        else:
            # both processes must also agree on flagged/post (whole dict)
            d0, d1 = json.loads(full[0]), json.loads(full[1])
            if d0 != d1:
                FINDINGS.append(
                    f"{rewriter}: finals equal but full result dicts differ: {d0} vs {d1}"
                )

    print("\n=== FINDINGS ===")
    if not FINDINGS:
        print("none — seed=42 reproduces byte-identically across fresh processes")
    for i, f in enumerate(FINDINGS, 1):
        print(f"{i}. {f}")
    return 1 if FINDINGS else 0


if __name__ == "__main__":
    sys.exit(main())
