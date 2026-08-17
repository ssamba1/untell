"""Slice 18 (wave 4, issue #22): mage FPR-vs-cut calibration curves.

Reuses the EXACT load path of `eval.detector_audit --pairs` — `eval.datasets.load_pairs`
plus `collapse_layout` — so the curves sit on the same measurement the shipped FPR
figures (README heavy-tier note) come from. Measures mage's human false-positive rate
and AI true-positive rate at every cut on HC3/RAID/MAGE paired corpora (30 pairs each).

NO THRESHOLDS ARE CHANGED. This script only measures; the recommendation is queued
(RED per the envelope: threshold moves are human decisions).

Usage:
    python .claude/probes/mage_calib_sweep.py [--corpus hc3,raid,mage] > sweep.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from eval.datasets import load_pairs  # noqa: E402
from eval.detector_audit import auroc, collapse_layout  # noqa: E402
from untell.detectors.mage import MageDetector  # noqa: E402


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs)


def measure_corpus(det, corpus: str, n: int = 30) -> dict | None:
    pairs = load_pairs(corpus, n)
    if not pairs:
        return None
    humans = [collapse_layout(h) for h, _ in pairs]
    ais = [collapse_layout(a) for _, a in pairs]
    hs = [x for x in (det.score(t) for t in humans) if isinstance(x, (int, float))]
    as_ = [x for x in (det.score(t) for t in ais) if isinstance(x, (int, float))]
    if not hs or not as_:
        return None
    cuts = [round(i / 100, 2) for i in range(101)]
    fpr_at = {c: sum(1 for h in hs if h >= c) / len(hs) for c in cuts}
    tpr_at = {c: sum(1 for a in as_ if a >= c) / len(as_) for c in cuts}
    # Smallest cut that holds human FPR <= 20% (the audit's MAX_FPR).
    fpr20 = next((c for c in cuts if fpr_at[c] <= 0.20), None)
    return {
        "corpus": corpus,
        "n_human": len(hs),
        "n_ai": len(as_),
        "human_scores": [round(x, 6) for x in sorted(hs)],
        "human_scores_ordered": [round(x, 6) for x in hs],
        "ai_scores": [round(x, 6) for x in sorted(as_)],
        "human_mean": round(_mean(hs), 4),
        "ai_mean": round(_mean(as_), 4),
        "auroc": round(auroc(as_, hs), 4) if auroc(as_, hs) is not None else None,
        "fpr_at_shipped_0_30": fpr_at[0.30],
        "tpr_at_shipped_0_30": tpr_at[0.30],
        "human_ge_0_83": sum(1 for h in hs if h >= 0.83),  # "upper mode" band from slice 11
        "human_ge_0_99": sum(1 for h in hs if h >= 0.99),
        "cut_for_fpr_le_0_20": fpr20,
        "tpr_at_fpr20_cut": tpr_at[fpr20] if fpr20 is not None else None,
        "curve": [
            {"cut": c, "fpr": round(fpr_at[c], 4), "tpr": round(tpr_at[c], 4)} for c in cuts
        ],
    }


def raid_pair_metadata(n: int = 30, min_words: int = 60, scan_cap: int = 60000) -> list[dict]:
    """Re-run _raid_pairs' exact selection, also keeping each human doc's domain/title.

    Deterministic given the corpus snapshot (streaming, attack=='none', same caps), so the
    doc order matches `load_pairs('raid', n)` and per-doc domains can be attributed to the
    scores the sweep measured.
    """
    from datasets import load_dataset

    ds = load_dataset("liamdugan/raid", split="train", streaming=True)
    humans: dict[str, str] = {}
    machines: dict[str, str] = {}
    meta: dict[str, dict] = {}
    pairs: list[dict] = []
    seen: set[str] = set()
    for i, row in enumerate(ds):
        if i >= scan_cap or len(pairs) >= n:
            break
        if (row.get("attack") or "none") != "none":
            continue
        text = (row.get("generation") or "").strip()
        key = row.get("source_id")
        if not text or not key or len(text.split()) < min_words:
            continue
        bucket = humans if row.get("model") == "human" else machines
        bucket.setdefault(key, text)
        meta.setdefault(key, {"domain": row.get("domain"), "title": row.get("title")})
        if key not in seen and key in humans and key in machines:
            seen.add(key)
            pairs.append({"human": humans[key], "ai": machines[key], **meta[key]})
    return pairs[:n]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus", default="hc3,raid,mage", help="comma-separated corpora")
    ap.add_argument("--pairs", type=int, default=30)
    ap.add_argument("--domains", action="store_true",
                    help="also print domain/title of each RAID human doc (re-selects pairs)")
    args = ap.parse_args()

    det = MageDetector()
    if not det.available():
        print("mage unavailable in this environment", file=sys.stderr)
        return 2

    out: dict = {"shipped_threshold": 0.30, "corpora": {}}
    for corpus in [c.strip() for c in args.corpus.split(",") if c.strip()]:
        res = measure_corpus(det, corpus, args.pairs)
        if res is None:
            print(f"{corpus}: no pairs loaded", file=sys.stderr)
            return 3
        out["corpora"][corpus] = res
        print(
            f"{corpus:6} n={res['n_human']:2} hm={res['human_mean']:.4f} "
            f"am={res['ai_mean']:.4f} AUROC={res['auroc']} "
            f"FPR@0.30={res['fpr_at_shipped_0_30']:.4f} "
            f"cut(FPR<=0.20)={res['cut_for_fpr_le_0_20']} "
            f"TPR@that={res['tpr_at_fpr20_cut']}",
            file=sys.stderr,
        )
    if args.domains and "raid" in out["corpora"]:
        flagged = [
            (s, m["domain"], m["title"])
            for s, m in zip(
                out["corpora"]["raid"]["human_scores_ordered"], raid_pair_metadata(args.pairs)
            )
            if s >= 0.30
        ]
        out["raid_flagged_metadata"] = [
            {"score": s, "domain": d, "title": (t or "")[:80]} for s, d, t in flagged
        ]
        print(
            f"RAID flagged at 0.30: {len(flagged)}/{args.pairs} — "
            f"domains: {[d for _, d, _ in flagged]}",
            file=sys.stderr,
        )
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
