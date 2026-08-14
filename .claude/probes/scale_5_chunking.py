"""scale_5_chunking.py — chunking ceiling: split_sentences + aligned_chunks at scale.

Measures at 10k / 100k / 1M chars:
  (a) split_sentences: sentence count ("chunks"), wall time -> scaling exponent
  (b) aligned_chunks(a, a): chunk pair count, consistency (rejoin == input,
      per-chunk word cap), wall time -> scaling exponent
  (c) adversarial aligned_chunks: two docs with shuffled word order (worst case
      for difflib.SequenceMatcher) at 10k/100k chars

Usage: python scale_5_chunking.py
"""
import json
import math
import os
import random
import time

from untell.text_split import aligned_chunks, split_sentences

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


def make_chars(n_chars: int) -> str:
    parts, total = [], 0
    i = 0
    while total < n_chars:
        s = _TEMPLATES[i % len(_TEMPLATES)] + " "
        parts.append(s)
        total += len(s)
        i += 1
    return "".join(parts)[:n_chars]


def loglog_fit(xs, ys):
    pts = [(x, y) for x, y in zip(xs, ys) if x > 0 and y > 0]
    n = len(pts)
    if n < 2:
        return float("nan"), float("nan")
    lx = [math.log(p[0]) for p in pts]
    ly = [math.log(p[1]) for p in pts]
    mx, my = sum(lx) / n, sum(ly) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(lx, ly))
    sxx = sum((a - mx) ** 2 for a in lx)
    syy = sum((b - my) ** 2 for b in ly)
    b = sxy / sxx if sxx else float("nan")
    r2 = (sxy * sxy / (sxx * syy)) if sxx and syy else float("nan")
    return b, r2


def main():
    out = {"split_sentences": {}, "aligned_chunks": {}, "adversarial_aligned": {}}
    sizes = [10_000, 100_000, 1_000_000]

    # (a) split_sentences
    ss_times, ss_counts = {}, {}
    for n in sizes:
        doc = make_chars(n)
        t0 = time.perf_counter()
        sents = split_sentences(doc)
        dt = time.perf_counter() - t0
        ss_times[n] = dt
        ss_counts[n] = len(sents)
        rejoined = " ".join(sents)
        out["split_sentences"][str(n)] = {
            "sentences": len(sents), "seconds": round(dt, 3),
            "consistent": abs(len(rejoined) - len(doc.strip())) / max(len(doc), 1) < 0.05,
        }
        print(f"split_sentences {n:>8,} chars: {len(sents):,} chunks in {dt:.3f}s", flush=True)
    b, r2 = loglog_fit(list(ss_times.keys()), list(ss_times.values()))
    out["split_sentences"]["scaling_exponent"] = round(b, 3)
    out["split_sentences"]["r2"] = round(r2, 4)
    print(f"split_sentences exponent: {b:.3f} R^2={r2:.4f}", flush=True)

    # (b) aligned_chunks(a, a) — identical sides (typical gate input)
    ac_times = {}
    for n in sizes:
        doc = make_chars(n)
        t0 = time.perf_counter()
        pairs = aligned_chunks(doc, doc)
        dt = time.perf_counter() - t0
        ac_times[n] = dt
        max_words = max((len(a.split()) for a, _ in pairs), default=0)
        n_words = len(doc.split())
        out["aligned_chunks"][str(n)] = {
            "chunk_pairs": len(pairs), "seconds": round(dt, 3),
            "max_chunk_words": max_words, "total_words": n_words,
            "consistent": all(a == b for a, b in pairs),
        }
        print(f"aligned_chunks({n:>8,} chars, identical): {len(pairs):,} pairs in {dt:.3f}s "
              f"(max chunk {max_words} words)", flush=True)
    b, r2 = loglog_fit(list(ac_times.keys()), list(ac_times.values()))
    out["aligned_chunks"]["scaling_exponent"] = round(b, 3)
    out["aligned_chunks"]["r2"] = round(r2, 4)
    print(f"aligned_chunks exponent: {b:.3f} R^2={r2:.4f}", flush=True)

    # (c) adversarial: same words, shuffled order (difflib worst-ish case)
    rng = random.Random(1)
    for n in (10_000, 100_000):
        doc = make_chars(n)
        words = doc.split()
        rng.shuffle(words)
        shuffled = " ".join(words)
        t0 = time.perf_counter()
        pairs = aligned_chunks(doc, shuffled)
        dt = time.perf_counter() - t0
        out["adversarial_aligned"][str(n)] = {"chunk_pairs": len(pairs), "seconds": round(dt, 3)}
        print(f"aligned_chunks SHUFFLED {n:>8,} chars: {len(pairs):,} pairs in {dt:.3f}s", flush=True)
    if "100000" in out["adversarial_aligned"] and "10000" in out["adversarial_aligned"]:
        t10 = out["adversarial_aligned"]["10000"]["seconds"]
        t100 = out["adversarial_aligned"]["100000"]["seconds"]
        if t10 > 0 and t100 > 0:
            out["adversarial_aligned"]["exp_10x_ratio"] = round(math.log(t100 / t10) / math.log(10), 2)

    print(json.dumps(out))


if __name__ == "__main__":
    main()
