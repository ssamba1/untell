"""NOVEL probe: ensemble selection-key live measurement.

The fleet's selkey.py probed the (max,mean) selection key statically. This measures
it LIVE: does the max-rewriter actually pick candidates that beat the saturated max,
and what does the selection key see vs what the verdict reports?

Fleet context: full-hc3-max measured pre 1.0 -> post 0.9758 — the selector DID find
winners. This probe digs into WHY: log every candidate score during a rewrite and
count how often `cand < best` fires (the selector's core decision).
"""
import sys, random
from pathlib import Path
for p in Path(__file__).resolve().parents:
    if (p / "untell" / "__init__.py").exists():
        sys.path.insert(0, str(p)); break

import untell.scripts.score as score_mod
from untell.scripts.run import untell_text
from untell.rewriter import composite

random.seed(1234)

TEXT = ("The results demonstrate significant improvements across all metrics. "
        "Moreover, the data indicate a clear trend toward enhanced performance. "
        "Furthermore, leveraging robust methodologies optimizes crucial outcomes. "
        "Additionally, the findings suggest that further investigation is warranted.")

# 1. What does the selection key see at each iteration?
r = untell_text(TEXT, tier='lite', max_iters=3, progress=False, seed=7)
print(f"final differs from src: {r['final'] != TEXT}")
print(f"pre_max={r.get('pre_max')} post_max={r.get('post_max')}")

# 2. Count cand<best firings by instrumenting the selector via monkeypatch
orig_select = composite.CompositeRewriter.select if hasattr(composite.CompositeRewriter, 'select') else None
print(f"has select method: {orig_select is not None}")
print(f"composite attrs: {[a for a in dir(composite.CompositeRewriter) if not a.startswith('_')][:12]}")
