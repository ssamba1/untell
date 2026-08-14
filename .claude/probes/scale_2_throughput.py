"""scale_2_throughput.py — score_text words/sec + scaling fit + tracemalloc peak.

One process, warm detector. Measures:
  (a) throughput at 100 / 1k / 10k words (words/sec, chars/sec)
  (b) runtime vs doc length over 1k..100k chars -> log-log fit (scaling exponent)
  (c) tracemalloc peak for a 100k-char doc (and a 1M-char doc through truncation)

Usage: python scale_2_throughput.py
"""
import json
import os
import time
import tracemalloc

os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.score import score_text  # noqa: E402

_TEMPLATES = [
    "The experiment measured variance across three conditions, and the results confirmed the hypothesis.",
    "Researchers observed a modest but consistent effect in the second cohort of participants.",
    "Further analysis revealed that the control group differed significantly from the treatment group.",
    "These findings suggest that the mechanism operates through a cascade of intermediate signals.",
    "A follow-up study replicated the outcome using an independent sample and identical instrumentation.",
    "The authors note that limitations in the sampling frame may constrain the generalizability of the results.",
    "Discussion of the implications centered on practical applications for clinical settings.",
    "Nevertheless, the magnitude of the observed effect warrants cautious interpretation.",
]


def make_words(n_words: int) -> str:
    parts, total = [], 0
    i = 0
    while total < n_words:
        s = _TEMPLATES[i % len(_TEMPLATES)]
        parts.append(s)
        total += len(s.split())
        i += 1
    return " ".join(parts)


def make_chars(n_chars: int) -> str:
    parts, total = [], 0
    i = 0
    while total < n_chars:
        s = _TEMPLATES[i % len(_TEMPLATES)] + " "
        parts.append(s)
        total += len(s)
        i += 1
    return "".join(parts)[:n_chars]


def best_of(fn, reps=3):
    ts = []
    for _ in range(reps):
        t0 = time.perf_counter()
        fn()
        ts.append(time.perf_counter() - t0)
    return min(ts)


def loglog_fit(xs, ys):
    """fit log y = a + b log x over points where x>0, y>0; return (b, r2)."""
    pts = [(x, y) for x, y in zip(xs, ys) if x > 0 and y > 0]
    n = len(pts)
    if n < 2:
        return float("nan"), float("nan")
    lx = [__import__("math").log(p[0]) for p in pts]
    ly = [__import__("math").log(p[1]) for p in pts]
    mx, my = sum(lx) / n, sum(ly) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(lx, ly))
    sxx = sum((a - mx) ** 2 for a in lx)
    syy = sum((b - my) ** 2 for b in ly)
    b = sxy / sxx if sxx else float("nan")
    r2 = (sxy * sxy / (sxx * syy)) if sxx and syy else float("nan")
    return b, r2


def main():
    # warm up (cold start is measured by scale_4)
    score_text("This is a warm-up sentence. " * 10, tier="lite")
    score_text("This is a warm-up sentence. " * 10, tier="lite")

    results = {"throughput": {}, "scaling": {}, "memory": {}}

    # (a) throughput at 100 / 1k / 10k words
    for nw in (100, 1_000, 10_000):
        doc = make_words(nw)
        dt = best_of(lambda: score_text(doc, tier="lite"), reps=3)
        eff_words = len(doc.split())
        results["throughput"][str(nw)] = {
            "input_words": nw,
            "effective_words": eff_words,
            "chars": len(doc),
            "seconds": round(dt, 4),
            "words_per_sec": round(eff_words / dt, 1),
            "chars_per_sec": round(len(doc) / dt, 1),
        }
        print(f"throughput {nw:>6,}w: {dt:.3f}s  {eff_words / dt:,.0f} words/s "
              f"({len(doc):,} chars)", flush=True)

    # (b) scaling: runtime vs char length (warm), fit <=50k (the real scored region)
    lengths = [1_000, 5_000, 10_000, 25_000, 50_000, 100_000]
    times = {}
    for n in lengths:
        doc = make_chars(n)
        dt = best_of(lambda: score_text(doc, tier="lite"), reps=3)
        times[n] = dt
        print(f"scaling {n:>7,} chars: {dt:.4f}s", flush=True)

    sub50 = [(n, times[n]) for n in lengths if n <= 50_000]
    b, r2 = loglog_fit([p[0] for p in sub50], [p[1] for p in sub50])
    b_all, r2_all = loglog_fit(list(times.keys()), list(times.values()))
    results["scaling"] = {
        "times": {str(k): round(v, 4) for k, v in times.items()},
        "exponent_le50k": round(b, 3),
        "r2_le50k": round(r2, 4),
        "exponent_all": round(b_all, 3),
        "r2_all": round(r2_all, 4),
        "note": "score_text truncates at 50k chars, so >50k points should plateau (exponent -> 0)",
    }
    print(f"scaling exponent (<=50k): {b:.3f}  R^2={r2:.4f} | all points: {b_all:.3f} R^2={r2_all:.4f}",
          flush=True)

    # (c) memory: tracemalloc peak
    for n in (100_000, 1_000_000):
        doc = make_chars(n)
        tracemalloc.start()
        t0 = time.time()
        score_text(doc, tier="lite")
        dt = time.time() - t0
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        results["memory"][str(n)] = {
            "seconds": round(dt, 3),
            "tracemalloc_peak_bytes": peak,
            "tracemalloc_peak_mb": round(peak / 1e6, 1),
        }
        print(f"memory {n:>8,} chars: peak {peak/1e6:,.1f} MB traced, {dt:.2f}s", flush=True)

    print(json.dumps(results))


if __name__ == "__main__":
    main()
