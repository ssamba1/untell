"""Slice 12: benchmark untell's engine per-document on the packaged corpora.

Measures, per document: wall time for the full loop (score -> rewrite -> re-score),
adoption (did the loop rewrite it), and pre/post flag rate at the default threshold.
Runs the SAME pipeline eval.ceiling drives (lite tier, composite rewriter) so the
numbers line up with the L8 recipes (length-short / length-long / human-false-positives).

Two modes, selected by env:
  UNTELL_LITE_NO_TORCH=1  -> stdlib lite path (the "true lite" the tier is documented as)
  (unset)                 -> torch present: perplexity_burstiness silently upgrades to
                             GPT-2 perplexity. This is the L3 lesson measured: torch
                             presence changes what "lite" runs.

Usage:
  UNTELL_LITE_NO_TORCH=1 .venv/Scripts/python.exe .claude/probes/slice12_corpus_bench.py
  MAX_ITERS=2 .venv/Scripts/python.exe .claude/probes/slice12_corpus_bench.py   # torch path subset
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
CORPORA = ROOT / ".claude" / "corpora"

MAX_ITERS = int(os.environ.get("MAX_ITERS", "2"))
BEST_OF = 1
TIER = "lite"
THRESHOLD = 0.3

from untell.rewriter import get_rewriter
from untell.scripts.run import untell_text
from untell.scripts.score import score_text

REWRITER = get_rewriter(prefer="composite")


def docs(path: Path) -> list[str]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    return [b.strip() for b in raw.split("\n\n") if b.strip()]


def run_corpus(path: Path) -> dict:
    texts = docs(path)
    rows = []
    for i, t in enumerate(texts):
        t0 = time.monotonic()
        pre = score_text(t, tier=TIER, threshold=THRESHOLD)
        res = untell_text(
            t, tier=TIER, threshold=THRESHOLD, max_iters=MAX_ITERS,
            rewriter=REWRITER, best_of=BEST_OF,
        )
        dt = time.monotonic() - t0
        post = res.get("post") or {}
        pre_max = pre.get("max")
        post_max = post.get("max")
        rewrote = bool(res.get("rewrites")) or res.get("final", t) != t
        rows.append({
            "doc": i + 1,
            "words": len(t.split()),
            "seconds": round(dt, 2),
            "pre_max": pre_max,
            "post_max": post_max,
            "pre_flagged": bool(pre_max is not None and pre_max >= THRESHOLD),
            "post_flagged": bool(post_max is not None and post_max >= THRESHOLD),
            "rewrote": rewrote,
            "rewrites": res.get("rewrites"),
            "similarity": res.get("similarity"),
        })
    n = len(rows)
    return {
        "file": path.name,
        "n_docs": n,
        "mode": "stdlib" if os.environ.get("UNTELL_LITE_NO_TORCH") == "1" else "torch-gpt2",
        "max_iters": MAX_ITERS,
        "total_seconds": round(sum(r["seconds"] for r in rows), 2),
        "mean_doc_seconds": round(sum(r["seconds"] for r in rows) / n, 2),
        "median_doc_seconds": round(sorted(r["seconds"] for r in rows)[n // 2], 2),
        "adoption_rate": round(sum(1 for r in rows if r["rewrote"]) / n, 3),
        "pre_flagged_rate": round(sum(1 for r in rows if r["pre_flagged"]) / n, 3),
        "post_flagged_rate": round(sum(1 for r in rows if r["post_flagged"]) / n, 3),
        "mean_similarity": round(
            sum(r["similarity"] for r in rows if r["similarity"] is not None)
            / sum(1 for r in rows if r["similarity"] is not None), 3)
        if any(r["similarity"] is not None for r in rows) else None,
        "rows": rows,
    }


def main() -> int:
    out = []
    for name in ("hc3-short.txt", "hc3-long.txt", "hc3-human.txt"):
        p = CORPORA / name
        if not p.exists():
            print(f"MISSING {p}")
            continue
        r = run_corpus(p)
        out.append(r)
        print(json.dumps(r, indent=1))
    Path(ROOT / ".claude" / "probes" / "slice12_bench_results.jsonl").write_text(
        "\n".join(json.dumps(r) for r in out) + "\n", encoding="utf-8")
    print("\nwrote .claude/probes/slice12_bench_results.jsonl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
