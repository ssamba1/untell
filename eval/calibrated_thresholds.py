"""Length-conditioned verdict thresholds, calibrated on text that cannot be AI-generated.

Roadmap item 18, and the tool's worst published number is the reason it matters. `flagged` compares
a document's score against **one fixed bar, 0.45**, chosen from a plateau in a ROC sweep. A single
bar assumes the score distribution of human writing does not depend on length. It does, badly:
this repo separately measures **28.69%** of 60-100 word pre-ChatGPT abstracts flagged against
**12.77%** above 200 — human text, by construction, so both figures are false-positive rates.

**A student handing in a short answer and a student handing in an essay are being judged by
different standards while the tool reports one.** That is not a calibration nicety; it is the
fairness failure the whole §4 literature is about, produced by the tool itself.

WHAT THIS DOES. Split the human corpus by word-count band, and inside each band take the empirical
quantile of the score distribution that leaves a chosen false-positive rate. That is the
distribution-free half of conformal prediction: with `n` calibration points, the `ceil((n+1)(1-a))`-th
smallest score is a threshold whose FPR is at most `a` on exchangeable future documents, with no
assumption about the score's shape. Reported per band, beside the fixed bar, with the sensitivity it
costs.

⚠️ **CONTROLLING FALSE POSITIVES IS FREE IF YOU NEVER MEASURE WHAT IT COSTS.** Any threshold can be
raised until nothing is flagged. Every row here therefore carries the true-positive rate on
machine-written text at the same bar, and a calibration that buys a lower FPR by discarding all
detection says so in the same table. The honest summary of a calibration is the PAIR.

⚠️ **The exchangeability assumption is the load-bearing one and it is not testable here.** The
guarantee holds for future documents drawn like the calibration set. The calibration set is ACL
abstracts: one register, one field, one era. A threshold calibrated here is a threshold for academic
abstracts, and applying it to student essays or forum posts imports an assumption this corpus cannot
check. That is stated in the output rather than buried.

    python -m eval.calibrated_thresholds --n 800
    python -m eval.calibrated_thresholds --all --target 0.05 --json
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# The bar `untell.scripts.score` ships. Read from the source of truth rather than repeated, so this
# module cannot drift from the number it is arguing about.
def shipped_threshold() -> float:
    from untell.scripts.score import score_text

    return float(score_text("a b c d e f g h i j k l m n o p", tier="lite")["verdict_threshold"])


def conformal_quantile(scores: list[float], target_fpr: float) -> float:
    """The split-conformal threshold: at most `target_fpr` of exchangeable future humans flagged.

    `ceil((n + 1)(1 - a)) / n` rather than the plain `(1 - a)` quantile. The `+1` is the finite-sample
    correction that makes the guarantee hold for a FUTURE document rather than for the calibration
    set itself — without it the bar is fitted to the very points it is evaluated on, and the promised
    rate is optimistic by roughly `1/n`. On a 200-document band that is half a percentage point, on a
    30-document band it is three, and the small bands are where this tool's error is worst.
    """
    if not scores:
        return float("nan")
    ordered = sorted(scores)
    n = len(ordered)
    rank = math.ceil((n + 1) * (1 - target_fpr))
    if rank > n:
        # Not enough calibration points to certify a rate this low: the honest bar is above every
        # score observed, and the caller is told the band is under-powered rather than handed a
        # threshold the data cannot support.
        return float("inf")
    return ordered[rank - 1]


def _scores(texts: list[str], tier: str) -> list[tuple[int, float]]:
    """(word count, detector max) per document."""
    from untell.scripts.score import score_text

    out = []
    for text in texts:
        result = score_text(text, tier=tier)
        values = [v for v in result["detectors"].values() if isinstance(v, (int, float))]
        if values:
            out.append((len(text.split()), max(values)))
    return out


def calibrate(human: list[str], machine: list[str], tier: str = "lite",
              target_fpr: float = 0.05) -> dict:
    """Per-band conformal thresholds, with the sensitivity each one costs.

    `human` must be text that cannot be AI-generated — the guarantee is only as good as that label,
    and this repo's pre-ChatGPT corpus is chosen precisely so the label needs no annotator.
    """
    from eval.pre_llm_fpr import LENGTH_BANDS, _band

    human_scored = _scores(human, tier)
    machine_scored = _scores(machine, tier)
    fixed = shipped_threshold()

    bands = []
    for low, high in LENGTH_BANDS:
        name = f"{low}-{high}" if high < 10**9 else f"{low}+"
        human_here = [s for w, s in human_scored if _band(w) == name]
        machine_here = [s for w, s in machine_scored if _band(w) == name]
        if not human_here:
            bands.append({"band": name, "n_human": 0,
                          "note": "no calibration documents in this band"})
            continue
        bar = conformal_quantile(human_here, target_fpr)
        fixed_fpr = sum(1 for s in human_here if s >= fixed) / len(human_here)
        cal_fpr = (sum(1 for s in human_here if s >= bar) / len(human_here)
                   if math.isfinite(bar) else 0.0)
        bands.append({
            "band": name,
            "n_human": len(human_here),
            "n_machine": len(machine_here),
            "fixed_threshold": round(fixed, 4),
            "calibrated_threshold": (round(bar, 4) if math.isfinite(bar) else None),
            "under_powered": not math.isfinite(bar),
            "fpr_at_fixed": round(fixed_fpr, 4),
            "fpr_at_calibrated": round(cal_fpr, 4),
            # The cost side. A threshold that flags nothing has a perfect false-positive rate.
            "tpr_at_fixed": (round(sum(1 for s in machine_here if s >= fixed) / len(machine_here), 4)
                             if machine_here else None),
            "tpr_at_calibrated": (
                round(sum(1 for s in machine_here if s >= bar) / len(machine_here), 4)
                if machine_here and math.isfinite(bar) else (0.0 if machine_here else None)),
            "mean_human_score": round(statistics.fmean(human_here), 4),
        })
    return {
        "tier": tier,
        "target_fpr": target_fpr,
        "fixed_threshold": round(fixed, 4),
        "n_human": len(human_scored),
        "n_machine": len(machine_scored),
        "bands": bands,
        "calibration_corpus": "ACL Anthology abstracts, volumes through 2021 (pre-ChatGPT)",
        "exchangeability_caveat":
            "The conformal guarantee holds for documents drawn like the calibration set. That set is "
            "academic abstracts in one field and era, so these thresholds are thresholds for "
            "academic abstracts. Applying them to essays or forum prose imports an assumption this "
            "corpus cannot check.",
    }


def _render(report: dict) -> str:
    lines = [
        f"Length-conditioned verdict thresholds, target FPR {report['target_fpr']:.0%}, "
        f"tier={report['tier']}.",
        f"Calibrated on {report['n_human']} documents that cannot be AI-generated; "
        f"{report['n_machine']} machine-written documents supply the sensitivity column.",
        "",
        f"{'band':>10}{'n':>7}{'fixed bar':>11}{'calib bar':>11}"
        f"{'FPR fixed':>11}{'FPR calib':>11}{'TPR fixed':>11}{'TPR calib':>11}",
    ]
    for row in report["bands"]:
        if row.get("note"):
            lines.append(f"{row['band']:>10}{row['n_human']:>7}   {row['note']}")
            continue
        bar = "under-powered" if row["under_powered"] else f"{row['calibrated_threshold']:.4f}"
        tpr_c = row["tpr_at_calibrated"]
        tpr_f = row["tpr_at_fixed"]
        lines.append(
            f"{row['band']:>10}{row['n_human']:>7}{row['fixed_threshold']:>11.4f}{bar:>11}"
            f"{row['fpr_at_fixed']:>11.1%}{row['fpr_at_calibrated']:>11.1%}"
            f"{(f'{tpr_f:.1%}' if tpr_f is not None else 'n/a'):>11}"
            f"{(f'{tpr_c:.1%}' if tpr_c is not None else 'n/a'):>11}"
        )
    lines += ["", "⚠️ " + report["exchangeability_caveat"]]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--n", type=int, default=800)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--tier", default="lite")
    parser.add_argument("--target", type=float, default=0.05, help="target false-positive rate")
    parser.add_argument("--cache", type=Path, default=REPO / ".anthology-cache")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    from eval.data.generated_abstracts import ABSTRACTS
    from eval.pre_llm_fpr import pre_llm_abstracts

    human = pre_llm_abstracts(args.cache)
    if not args.all:
        human = human[: args.n]
    report = calibrate(human, list(ABSTRACTS), args.tier, args.target)
    print(json.dumps(report, indent=2) if args.as_json else _render(report))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
