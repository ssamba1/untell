"""Probe 1: thread safety of score_text / lite detector under 8 concurrent threads.

- (a) ONE shared PerplexityBurstinessDetector instance scored from 8 threads;
      every result must equal the serial baseline exactly (no corruption).
- (b) score_text(tier='lite') full path from 8 threads; every JSON must be
      byte-identical to the serial baseline.
- (c) detector.mode() must stay 'stdlib' (no env/global mutation from threads).

Run:  PYTHONPATH= UNTELL_LITE_NO_TORCH=1 .venv/Scripts/python.exe .claude/probes/concurrency_score_threads.py
"""
from __future__ import annotations

import json
import sys
import threading
import time

from untell.detectors.perplexity_burstiness import PerplexityBurstinessDetector
from untell.scripts.score import score_text

TEXT = (
    "The advancement of artificial intelligence has revolutionized the way we approach "
    "complex problems across many domains. Researchers continue to develop increasingly "
    "sophisticated models that demonstrate remarkable capabilities in natural language "
    "understanding and generation. These systems have found practical applications in "
    "healthcare, education, and creative industries."
)

FINDINGS: list[str] = []


def canon(d: dict) -> str:
    return json.dumps(d, sort_keys=True, ensure_ascii=True, indent=2)


def main() -> int:
    # ---- serial baselines -------------------------------------------------
    det = PerplexityBurstinessDetector()
    base_score = det.score(TEXT)
    base_mode = det.mode()
    base_json = canon(score_text(TEXT, tier="lite"))
    print(f"[baseline] detector score={base_score!r} mode={base_mode!r}")

    errors: list[tuple[str, str]] = []

    # ---- (a) 8 threads, ONE shared detector instance ----------------------
    n_threads, per_thread = 8, 25
    results: list[list] = [[] for _ in range(n_threads)]
    mode_results: list[list] = [[] for _ in range(n_threads)]

    def worker_shared(idx: int) -> None:
        try:
            for _ in range(per_thread):
                results[idx].append(det.score(TEXT))
                mode_results[idx].append(det.mode())
        except Exception as e:  # noqa: BLE001
            errors.append((f"shared-worker-{idx}", repr(e)))

    t0 = time.time()
    threads = [threading.Thread(target=worker_shared, args=(i,)) for i in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    wall_a = time.time() - t0

    flat = [v for row in results for v in row]
    bad = [v for v in flat if v != base_score]
    bad_modes = [v for row in mode_results for v in row if v != base_mode]
    if bad:
        FINDINGS.append(
            f"RACE (a): {len(bad)}/{len(flat)} concurrent detector scores differ from "
            f"serial baseline {base_score!r}; e.g. {bad[:3]!r}"
        )
    if bad_modes:
        FINDINGS.append(f"RACE (a): mode() changed under concurrency: {bad_modes[:3]!r}")
    print(f"[a] shared-instance: {len(flat)} calls, {wall_a:.1f}s, mismatches={len(bad)}, mode-mismatches={len(bad_modes)}")

    # ---- (b) 8 threads, score_text(tier='lite') full path -----------------
    json_results: list[list] = [[] for _ in range(n_threads)]

    def worker_full(idx: int) -> None:
        try:
            for _ in range(per_thread):
                json_results[idx].append(canon(score_text(TEXT, tier="lite")))
        except Exception as e:  # noqa: BLE001
            errors.append((f"full-worker-{idx}", repr(e)))

    t0 = time.time()
    threads = [threading.Thread(target=worker_full, args=(i,)) for i in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    wall_b = time.time() - t0

    flat_json = [v for row in json_results for v in row]
    bad_json = [v for v in flat_json if v != base_json]
    if bad_json:
        FINDINGS.append(
            f"RACE (b): {len(bad_json)}/{len(flat_json)} concurrent score_text results "
            f"differ from serial baseline (JSON differs)"
        )
    print(f"[b] score_text path: {len(flat_json)} calls, {wall_b:.1f}s, mismatches={len(bad_json)}")

    # ---- (c) repeatability: same instance, serial, 100 calls ---------------
    serial_vals = {det.score(TEXT) for _ in range(100)}
    if len(serial_vals) != 1:
        FINDINGS.append(
            f"DETERMINISM: serial repeated scoring on one instance gave "
            f"{len(serial_vals)} distinct values: {list(serial_vals)[:4]!r}"
        )

    if errors:
        FINDINGS.append(f"EXCEPTIONS during concurrent scoring: {errors[:5]}")
        print(f"[errors] {len(errors)} exceptions: {errors[:5]}")
    else:
        print("[errors] none")

    print("\n=== FINDINGS ===")
    if not FINDINGS:
        print("none — scoring is thread-safe and deterministic on this path")
    for i, f in enumerate(FINDINGS, 1):
        print(f"{i}. {f}")
    return 1 if FINDINGS else 0


if __name__ == "__main__":
    sys.exit(main())
