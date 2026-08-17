"""Issue #40 probe: per-detector calibration curves at SENTENCE granularity on labelled HC3.

The loop's rewrite targeting scores sentences in isolation (`targeted.py`: flag when
`max(detector scores) >= min_score`, min_score=0.30) — see the slice-11 audit, where 4 of 5
detectors fired at FPR 33-57% on human sentences at that threshold. This probe measures the
actual FPR-vs-threshold curve for every locally-runnable detector at sentence granularity so
a calibration (per-detector threshold table) can be designed from data instead of guesswork.

Reuses the audit's data path exactly: `eval.datasets.load_pairs('hc3', n)`, layout collapse
(both halves — HC3's ChatGPT half is newline-formatted, its human half is not), sentence
split via `untell.text_split.split_sentences`, sentences < 10 words dropped (same rule as
`eval/detector_audit.py`). Sentences are capped at `--max-sentences` per class so the run
stays bounded (mage is ~4.6s/call warm).

Outputs (all saved, nothing printed-only):
  <out>/sentence_calibration_<ts>.json       raw per-sentence scores + derived curves

    usage: python .claude/probes/calibration_sweep.py [--pairs 40] [--max-sentences 60]
           [--out .claude/probes/evidence]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# Run-as-file support: put the package parent on sys.path when executed directly.
if __package__ in (None, ""):
    for _p in Path(__file__).resolve().parents:
        if (_p / "untell" / "__init__.py").exists():
            sys.path.insert(0, str(_p))
            break

from eval.datasets import load_pairs  # noqa: E402
from eval.detector_audit import auroc, collapse_layout  # noqa: E402
from untell.text_split import split_sentences  # noqa: E402

SHIPPED = 0.30  # DEFAULT_THRESHOLD in untell.scripts.score; targeted.py min_score

# Same locally-runnable set as eval/detector_audit.py. radar/local_judge/binoculars are
# opt-in UNAVAILABLE in this environment (as in slice 11).
_SPECS = [
    ("perplexity_burstiness", "untell.detectors.perplexity_burstiness", "PerplexityBurstinessDetector"),
    ("roberta_openai", "untell.detectors.roberta_openai", "RobertaOpenAIDetector"),
    ("hc3_roberta", "untell.detectors.hc3_roberta", "HC3RobertaDetector"),
    ("fast_detectgpt", "untell.detectors.fast_detectgpt", "FastDetectGPTDetector"),
    ("mage", "untell.detectors.mage", "MageDetector"),
]

# Fine threshold grid for the curves: 0.01 steps plus the shipped threshold. n=60/class gives
# an FPR resolution of ~1.7%, so anything finer than 0.01 is overkill for the curve itself.
GRID = sorted({round(i / 100, 2) for i in range(1, 100)} | {SHIPPED})


def _sentences_from(paragraphs: list[str], max_sentences: int) -> list[str]:
    out: list[str] = []
    for para in paragraphs:
        out += [s for s in split_sentences(para) if len(s.split()) >= 10]
    return out[:max_sentences]


def fpr_tpr(scores_human: list[float], scores_ai: list[float], t: float) -> tuple[float, float]:
    fpr = sum(1 for x in scores_human if x >= t) / len(scores_human)
    tpr = sum(1 for x in scores_ai if x >= t) / len(scores_ai)
    return fpr, tpr


def threshold_for_fpr(scores_human: list[float], target: float) -> float:
    """Largest threshold t (at 0.001 resolution) with FPR(t) <= target.

    Ties in the human scores can force a strictly lower threshold than the naive
    quantile — enumerate candidate thresholds between consecutive distinct scores so the
    answer is exact up to the grid resolution, not a quantile approximation.
    """
    uniq = sorted(set(scores_human))
    cands = [0.0] + uniq
    for a, b in zip(uniq, uniq[1:]):
        cands.append((a + b) / 2)
    best = 0.0
    for t in cands:
        if sum(1 for x in scores_human if x >= t) / len(scores_human) <= target:
            best = max(best, t)
    return round(best, 4)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", type=int, default=40, help="HC3 labelled pairs to load")
    ap.add_argument("--max-sentences", type=int, default=60, help="sentences per class")
    ap.add_argument("--out", default=Path(__file__).parent / "evidence")
    ap.add_argument("--json", action="store_true", help="dump the evidence object")
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    loaded = load_pairs("hc3", args.pairs)
    if not loaded:
        print(json.dumps({"error": "hc3 pairs unavailable"}, indent=2))
        return 1
    human_raw = [h for h, _ in loaded]
    ai_raw = [a for _, a in loaded]
    human_sents = _sentences_from([collapse_layout(h) for h in human_raw], args.max_sentences)
    ai_sents = _sentences_from([collapse_layout(a) for a in ai_raw], args.max_sentences)
    print(f"pairs={len(loaded)} sentences/class human={len(human_sents)} ai={len(ai_sents)}",
          flush=True)

    rows: list[dict] = []
    raw: dict[str, dict[str, list[float]]] = {}
    for key, module, cls in _SPECS:
        t0 = time.time()
        try:
            mod = __import__(module, fromlist=[cls])
            det = getattr(mod, cls)()
            if not det.available():
                rows.append({"detector": key, "verdict": "UNAVAILABLE"})
                continue
            human_scores = [det.score(s) for s in human_sents]
            ai_scores = [det.score(s) for s in ai_sents]
        except Exception as exc:  # noqa: BLE001 — probe must report, not crash the sweep
            rows.append({"detector": key, "verdict": f"SCORE_ERR:{type(exc).__name__}:{exc}"})
            continue
        human_scores = [x for x in human_scores if isinstance(x, (int, float))]
        ai_scores = [x for x in ai_scores if isinstance(x, (int, float))]
        if not human_scores or not ai_scores:
            rows.append({"detector": key, "verdict": "RETURNED_NONE"})
            continue
        raw[key] = {"human": human_scores, "ai": ai_scores}
        au = auroc(ai_scores, human_scores)
        fpr_s, tpr_s = fpr_tpr(human_scores, ai_scores, SHIPPED)
        t20 = threshold_for_fpr(human_scores, 0.20)
        t10 = threshold_for_fpr(human_scores, 0.10)
        fpr20, tpr20 = fpr_tpr(human_scores, ai_scores, t20)
        fpr10, tpr10 = fpr_tpr(human_scores, ai_scores, t10)
        curve = [
            {"t": t, "fpr": round(fpr_tpr(human_scores, ai_scores, t)[0], 4),
             "tpr": round(fpr_tpr(human_scores, ai_scores, t)[1], 4)}
            for t in GRID
        ]
        rows.append({
            "detector": key,
            "granularity": "sentence",
            "n_human": len(human_scores),
            "n_ai": len(ai_scores),
            "auroc": round(au, 4) if au is not None else None,
            "human_mean": round(sum(human_scores) / len(human_scores), 4),
            "ai_mean": round(sum(ai_scores) / len(ai_scores), 4),
            "fpr_at_shipped": round(fpr_s, 4),
            "tpr_at_shipped": round(tpr_s, 4),
            "t_for_fpr_0.20": t20,
            "fpr_at_t20": round(fpr20, 4),
            "tpr_at_t20": round(tpr20, 4),
            "t_for_fpr_0.10": t10,
            "fpr_at_t10": round(fpr10, 4),
            "tpr_at_t10": round(tpr10, 4),
            "seconds": round(time.time() - t0, 1),
        })
        print(f"  {key}: FPR@{SHIPPED}={fpr_s:.3f} TPR={tpr_s:.3f} "
              f"t(FPR<=.20)={t20} TPR={tpr20:.3f} ({time.time()-t0:.0f}s)", flush=True)

    evidence = {
        "probe": "issue-40 sentence-granularity calibration curves",
        "dataset": "hc3",
        "pairs": len(loaded),
        "max_sentences": args.max_sentences,
        "shipped_threshold": SHIPPED,
        "sentence_min_words": 10,
        "layout_collapsed": True,
        "git_head": _git_head(),
        "rows": rows,
        "raw_scores": raw,
    }
    ts = time.strftime("%Y%m%d_%H%M%S")
    path = out_dir / f"sentence_calibration_{ts}.json"
    path.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(f"evidence -> {path}", flush=True)
    if args.json:
        print(json.dumps(evidence, indent=2))
    return 0


def _git_head() -> str:
    import subprocess

    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=10
        )
        return out.stdout.strip()
    except Exception:  # noqa: BLE001
        return "unknown"


if __name__ == "__main__":
    sys.exit(main())
