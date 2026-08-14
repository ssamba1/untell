"""Probe 2: 4 concurrent untell_text rewrites — output stability + RNG hygiene.

- Warm up once (pays the one-time MiniLM/transformers import, ~60s).
- (a) 4 threads rewriting the SAME text with seed=42: all finals must be
      byte-identical to the serial baseline (the _RNG_LOCK should make this true).
- (b) 4 threads rewriting 4 DIFFERENT texts with seed=42: each must equal its own
      serial baseline (no cross-talk).
- (c) caller RNG must be restored: random.getstate() before == after each call.
- (d) wall-time: 4 concurrent vs 4 serial (expect ~serialised: GAP if ~4x).

Run:  PYTHONPATH= UNTELL_LITE_NO_TORCH=1 .venv/Scripts/python.exe .claude/probes/concurrency_rewrite_threads.py
"""
from __future__ import annotations

import random
import sys
import threading
import time

from untell.scripts.run import untell_text

TEXTS = {
    "t1": (
        "The advancement of artificial intelligence has revolutionized the way we approach "
        "complex problems across many domains. Researchers continue to develop increasingly "
        "sophisticated models that demonstrate remarkable capabilities."
    ),
    "t2": (
        "Climate change poses an existential threat to coastal communities worldwide. Rising sea "
        "levels and more frequent extreme weather events are forcing governments to reconsider "
        "long-term infrastructure planning and investment strategies."
    ),
    "t3": (
        "The rapid growth of remote work has transformed organizational culture in unexpected "
        "ways. Companies are now grappling with questions about productivity measurement, team "
        "cohesion, and the long-term viability of distributed collaboration models."
    ),
    "t4": (
        "Quantum computing promises to solve problems that are intractable for classical machines. "
        "Researchers are exploring applications in cryptography, drug discovery, and materials "
        "science, though practical implementations remain years away."
    ),
}

FINDINGS: list[str] = []


def run(text: str, seed: int) -> dict:
    return untell_text(
        text, tier="lite", rewriter="surgical", max_iters=1, best_of=1, seed=seed
    )


def main() -> int:
    print("[warmup] first call pays one-time imports ...")
    t0 = time.time()
    run(TEXTS["t1"], 42)
    print(f"[warmup] done in {time.time()-t0:.1f}s")

    # ---- serial baselines ---------------------------------------------------
    serial: dict[str, dict] = {}
    for name, text in TEXTS.items():
        serial[name] = run(text, 42)
    same_serial = [run(TEXTS["t1"], 42) for _ in range(3)]
    if any(r["final"] != serial["t1"]["final"] for r in same_serial):
        FINDINGS.append(
            "DETERMINISM: serial same-text seed=42 runs are NOT byte-identical "
            "(in-process reproducibility broken even without threads)"
        )
    print("[baselines] serial finals computed")

    # ---- (a) 4 threads, SAME text, seed=42 ----------------------------------
    results_a: list[dict] = [None] * 4
    errors_a: list[str] = []

    def worker_a(i: int) -> None:
        try:
            results_a[i] = run(TEXTS["t1"], 42)
        except Exception as e:  # noqa: BLE001
            errors_a.append(f"worker-a{i}: {e!r}")

    t0 = time.time()
    threads = [threading.Thread(target=worker_a, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    wall_a = time.time() - t0

    baseline = serial["t1"]["final"]
    bad_a = [i for i, r in enumerate(results_a) if r is None or r["final"] != baseline]
    if bad_a:
        FINDINGS.append(
            f"RACE (a): 4 concurrent same-text seed=42 rewrites; threads {bad_a} differ "
            f"from serial baseline (len {len(baseline)}). Diffs: "
            + "; ".join(
                f"thr{i}: len={len(results_a[i]['final']) if results_a[i] else 'EXC'}" for i in bad_a
            )
        )
    print(f"[a] same-text 4 threads: wall={wall_a:.1f}s mismatches={bad_a}")

    # ---- (b) 4 threads, DIFFERENT texts, seed=42 -----------------------------
    results_b: list[dict] = [None] * 4
    errors_b: list[str] = []
    names = list(TEXTS)

    def worker_b(i: int) -> None:
        try:
            results_b[i] = run(TEXTS[names[i]], 42)
        except Exception as e:  # noqa: BLE001
            errors_b.append(f"worker-b{i}: {e!r}")

    t0 = time.time()
    threads = [threading.Thread(target=worker_b, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    wall_b = time.time() - t0

    bad_b = [
        i for i, r in enumerate(results_b)
        if r is None or r["final"] != serial[names[i]]["final"]
    ]
    if bad_b:
        FINDINGS.append(
            f"RACE (b): 4 concurrent different-text seed=42 rewrites; texts {bad_b} differ "
            f"from their serial baselines (cross-talk)"
        )
    print(f"[b] different-text 4 threads: wall={wall_b:.1f}s mismatches={bad_b}")

    # ---- (c) RNG restore ------------------------------------------------------
    before = random.getstate()
    run(TEXTS["t1"], 42)
    after = random.getstate()
    if before != after:
        FINDINGS.append(
            "GLOBAL-STATE LEAK (c): untell_text does NOT restore the caller's "
            "random.getstate() (seeded region leaks RNG mutation)"
        )
    print(f"[c] RNG restored after call: {before == after}")

    # ---- (d) serialisation cost ----------------------------------------------
    t0 = time.time()
    for i in range(4):
        run(TEXTS[names[i]], 42)
    wall_serial = time.time() - t0
    print(f"[d] 4 serial rewrites: {wall_serial:.1f}s | 4 concurrent: {wall_a:.1f}s "
          f"(same text), {wall_b:.1f}s (diff text)")
    if wall_b > 1.6 * wall_serial:
        FINDINGS.append(
            f"GAP (d): concurrent rewrites are NOT faster than serial "
            f"({wall_b:.1f}s vs {wall_serial:.1f}s) — _RNG_LOCK fully serialises rewrites"
        )

    if errors_a or errors_b:
        FINDINGS.append(f"EXCEPTIONS: a={errors_a} b={errors_b}")

    print("\n=== FINDINGS ===")
    if not FINDINGS:
        print("none — concurrent rewrites are stable and RNG-hygienic")
    for i, f in enumerate(FINDINGS, 1):
        print(f"{i}. {f}")
    return 1 if FINDINGS else 0


if __name__ == "__main__":
    sys.exit(main())
