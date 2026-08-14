"""scale_3_rewrite_scaling.py — untell_text runtime vs doc length (the /humanize DoS surface).

The API caps requests at 50k chars, but untell_text (library / MCP / CLI) rewrites the
WHOLE doc: per iteration it runs the composite rewriter over every sentence AND the
similarity gate (aligned_chunks -> difflib.SequenceMatcher) over the full pair.
Fit log-log exponent over 1k..50k chars at max_iters=1, best_of=1.

Usage: python scale_3_rewrite_scaling.py
"""
import json
import math
import os
import time

os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.run import untell_text  # noqa: E402

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
    # warm up (detector construction + one small loop)
    untell_text(make_chars(500), tier="lite", max_iters=1, best_of=1, seed=1)

    lengths = [1_000, 2_000, 5_000, 10_000, 25_000, 50_000]
    times = {}
    for n in lengths:
        doc = make_chars(n)
        t0 = time.perf_counter()
        res = untell_text(doc, tier="lite", max_iters=1, best_of=1, seed=42)
        dt = time.perf_counter() - t0
        times[n] = dt
        print(f"untell_text {n:>7,} chars: {dt:.2f}s  iterations={res.get('iterations')} "
              f"flagged={res.get('flagged')} sim={res.get('similarity')}", flush=True)

    b, r2 = loglog_fit(list(times.keys()), list(times.values()))
    print(json.dumps({
        "times": {str(k): round(v, 3) for k, v in times.items()},
        "scaling_exponent": round(b, 3),
        "r2": round(r2, 4),
        "params": {"max_iters": 1, "best_of": 1, "tier": "lite"},
        "defect": b > 1.2,
        "note": "exponent > 1.2 = superlinear; untell_text runs the FULL doc through the "
                "rewriter + similarity gate every iteration (API /humanize caps at 50k chars "
                "with 422, but library/MCP paths do not)",
    }))


if __name__ == "__main__":
    main()
