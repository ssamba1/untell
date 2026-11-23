"""Recommended thresholds for open detectors: fitted on one human corpus, evaluated on another.

A detector's default 0.5 is a training artefact, not a decision about how many honest writers to
accuse. This sets each detector's threshold so that at most ``target_fpr`` of a FIT corpus of
pre-2022 human writing is flagged — the same fit corpus untell's own calibration v2 uses (868
documents: five software projects' docs and 600 PERSUADE essays, half by English learners) — and
then reports, untouched, what that threshold does on held-out corpora, using the per-document
scores already stored in each detector's report card.

    python -m untell.bench.thresholds hf_fit.json docs/observatory/open-detectors \\
        --out docs/observatory/open-detectors/thresholds.json
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from untell.evidence.stats import threshold_at_fpr, wilson_interval


def _rate(k: int, n: int) -> dict:
    lo, hi = wilson_interval(k, n) if n else (None, None)
    return {"k": k, "n": n, "rate": k / n if n else None, "ci95": [lo, hi]}


def evaluate(card: dict, threshold: float) -> dict:
    by: dict[str, list] = defaultdict(list)
    for r in card["documents"]:
        if r["score"] is not None:
            by[(r["label"], r["group"])].append(r["score"])
    groups = {g: {"label": lab, "default": _rate(sum(s >= 0.5 for s in xs), len(xs)),
                  "recommended": _rate(sum(s >= threshold for s in xs), len(xs))}
              for (lab, g), xs in sorted(by.items())}
    ai = [s for (lab, _), xs in by.items() if lab == "ai" for s in xs]
    hum = [s for (lab, _), xs in by.items() if lab == "human" for s in xs]
    return {"groups": groups,
            "human": {"default": _rate(sum(s >= 0.5 for s in hum), len(hum)),
                      "recommended": _rate(sum(s >= threshold for s in hum), len(hum))},
            "ai_recall": {"default": _rate(sum(s >= 0.5 for s in ai), len(ai)),
                          "recommended": _rate(sum(s >= threshold for s in ai), len(ai))}}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m untell.bench.thresholds", description=__doc__.split("\n\n")[0])
    ap.add_argument("fit_scores", help="JSON {model: [{id, score}]} on the fit corpus")
    ap.add_argument("cards", help="folder of open-detector report cards (held-out scores)")
    ap.add_argument("--target-fpr", type=float, default=0.05)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    fit = json.loads(Path(args.fit_scores).read_text(encoding="utf-8"))
    out = {"target_fpr": args.target_fpr,
           "fit_corpus": "868 pre-2022 human documents (calibration v2's fit corpus)", "models": {}}
    for model, rows in fit.items():
        card_path = Path(args.cards) / (model.replace("/", "__") + ".json")
        if not card_path.exists():
            continue
        thr = threshold_at_fpr([r["score"] for r in rows], args.target_fpr)
        card = json.loads(card_path.read_text(encoding="utf-8"))
        out["models"][model] = {"threshold": thr, "fit_n": len(rows), "held_out": evaluate(card, thr)}
        h = out["models"][model]["held_out"]
        print(f"{model:48} threshold {thr:.4f}  human FPR {h['human']['default']['rate']:.3f} -> "
              f"{h['human']['recommended']['rate']:.3f}  AI recall {h['ai_recall']['default']['rate']:.3f}"
              f" -> {h['ai_recall']['recommended']['rate']:.3f}")
    Path(args.out).write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
