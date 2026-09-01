"""Measure what a detector does to writers furthest from a corpus's norm — without asking anyone.

Every fairness arm in this repository needs a protected attribute: `eval/assisted_fairness.py`
stratifies by an author-status column, and status row 28 (detectors against neurodivergent and
disabled writers) has stayed open since round sixteen because no corpus carries that label with
consent. Asking applicants to declare a disability so a detector can be audited against them is not
a workable protocol, and it is not one this project would propose.

*Centering the Margins* (Mendelsohn et al., 2023.emnlp-main.579) supplies the way around it. Drawing
on disability studies — "people farther from the norm face greater adversity" — it operationalises
the margins of a dataset **by outlier detection**, finding text about people whose attributes are
distant from the norm rather than by subgroup label, and reports toxicity-model error up to 70.4%
worse for those outliers. That paper is about toxicity detection; this module is the same method
pointed at AI-text detection, which as of round thirty nobody has published.

It is also DivScore (2025.emnlp-main.971) from the other end. DivScore ties zero-shot detector
failure to the divergence between a text's distribution and the detector's reference; this measures
distance from the *corpus's* centre and asks whether the false-positive rate rises with it. Both say
the risk is distance from a norm, and neither needs to know why a given writer is distant — which is
the point, because "further from the norm" collects non-native writers, disabled writers, unusual
subject matter and anyone with a strong idiolect, without requiring them to be identified.

**What this can and cannot show.** Run on pre-LLM text, every flag is a false positive by
construction, so a gap between outliers and the rest is a real disparity in false accusations. It
does NOT say which attribute drives it — outlier status is not a protected characteristic, and this
module never claims a text belongs to any group.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from pathlib import Path

from eval.pre_llm_fpr import pre_llm_abstracts, wilson_interval

_WORD = re.compile(r"[A-Za-z']+")
_SENT = re.compile(r"[.!?]+\s+")


def features(text: str) -> dict[str, float]:
    """Stylometric features, all pure stdlib.

    Deliberately the plainest possible set: anything needing a model would put this behind the same
    egress wall that keeps the ML detectors from loading, and an audit nobody can run is not an
    audit. These are the axes the resume-corpus paper (2026.lrec-1.581) reports separating its
    classes — length, lexical diversity, sentence uniformity, punctuation — so they are at least the
    right family.
    """
    words = _WORD.findall(text.lower())
    if not words:
        return {"words": 0.0, "ttr": 0.0, "mean_word_len": 0.0, "sent_len_cv": 0.0, "punct_rate": 0.0}
    sentences = [s for s in _SENT.split(text) if s.strip()] or [text]
    lengths = [len(_WORD.findall(s)) for s in sentences]
    mean_len = statistics.fmean(lengths) if lengths else 0.0
    sd = statistics.pstdev(lengths) if len(lengths) > 1 else 0.0
    return {
        "words": float(len(words)),
        "ttr": len(set(words)) / len(words),
        "mean_word_len": statistics.fmean(len(w) for w in words),
        # Coefficient of variation of sentence length — "burstiness" by another name, and the one
        # feature here the detectors themselves also use.
        "sent_len_cv": (sd / mean_len) if mean_len else 0.0,
        "punct_rate": sum(c in ",;:—-()" for c in text) / max(len(words), 1),
    }


def outlier_scores(texts: list[str]) -> list[float]:
    """Distance from the corpus centre, as a mean absolute z-score across features.

    Robust statistics on purpose: the median and the median absolute deviation, not the mean and
    standard deviation. The outliers are what is being measured, and letting them set the centre and
    the scale is how an outlier analysis quietly reports that nothing is unusual.
    """
    rows = [features(t) for t in texts]
    keys = [k for k in rows[0] if k != "words"] + ["words"]
    centre, scale = {}, {}
    for key in keys:
        values = [r[key] for r in rows]
        med = statistics.median(values)
        mad = statistics.median([abs(v - med) for v in values]) or 1e-9
        centre[key], scale[key] = med, mad
    return [
        statistics.fmean(abs(r[key] - centre[key]) / scale[key] for key in keys) for r in rows
    ]


def _score_all(texts: list[str], tier: str) -> tuple[list[float], list[int], set[str], list[str]]:
    """Score every text once. Split it many ways afterwards.

    Separated from `probe_by_distance` so `probe_sweep` can vary the margin cut-off without paying
    for the scoring again — which is what makes the sensitivity analysis cheap enough to always run.
    """
    from untell.scripts.score import score_text

    distances = outlier_scores(texts)
    kept_distance: list[float] = []
    flags: list[int] = []
    detectors_seen: set[str] = set()
    # The kept TEXTS are returned alongside, not just the counts. A caller that re-pairs texts with
    # flags positionally is correct only while nothing is dropped, and a detector returning no
    # agreement for one document silently shifts every flag after it onto the wrong text. That is a
    # wrong answer with no error, which is the worst shape a bug can take here.
    kept_texts: list[str] = []
    for text, distance in zip(texts, distances):
        result = score_text(text, tier=tier)
        spread = result.get("agreement")
        if not spread:
            continue
        detectors_seen.update(
            n for n, v in result["detectors"].items() if isinstance(v, (int, float))
        )
        kept_distance.append(distance)
        flags.append(int(bool(spread["any"])))
        kept_texts.append(text)
    return kept_distance, flags, detectors_seen, kept_texts


def _split(distances: list[float], flags: list[int], quantile: float) -> tuple[dict, dict, float]:
    """False-positive rates either side of the margin cut, with Wilson intervals."""
    cut = sorted(distances, reverse=True)[max(1, int(len(distances) * quantile)) - 1]
    margin = [f for d, f in zip(distances, flags) if d >= cut]
    centre = [f for d, f in zip(distances, flags) if d < cut]

    def _rate(hits: list[int]) -> dict:
        low, high = wilson_interval(sum(hits), len(hits))
        return {
            "n": len(hits),
            "flagged": sum(hits),
            "fpr": round(sum(hits) / len(hits), 4) if hits else None,
            "ci95": [round(low, 4), round(high, 4)],
        }

    return _rate(margin), _rate(centre), cut


# Where to draw the line between "the margins" and "everyone else" is a free parameter, and a gap
# that only appears at one setting of a free parameter is not a gap. Reported across all of these
# every time, so the choice cannot be made after seeing the answer.
SWEEP_QUANTILES: tuple[float, ...] = (0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40)


def probe_sweep(texts: list[str], tier: str = "lite") -> dict:
    """The same comparison at every margin cut-off, from the furthest 5% to the furthest 40%.

    This is the analysis that decides whether `probe_by_distance`'s headline is worth anything. If
    the gap flips sign, or appears only at one cut, the honest reading is that the corpus has no
    disparity and the single number was a choice.
    """
    if len(texts) < 10:
        return {"n": len(texts), "error": "need at least 10 texts to split a corpus into margins"}
    distances, flags, detectors, _ = _score_all(texts, tier)
    rows = []
    for q in SWEEP_QUANTILES:
        margin, centre, _ = _split(distances, flags, q)
        comparable = margin["n"] >= 5 and centre["n"] >= 5
        rows.append({
            "quantile": q,
            "margin": margin,
            "centre": centre,
            "gap": (round(margin["fpr"] - centre["fpr"], 4)
                    if comparable and None not in (margin["fpr"], centre["fpr"]) else None),
            "intervals_overlap": (
                None if not comparable
                else not (margin["ci95"][0] > centre["ci95"][1]
                          or centre["ci95"][0] > margin["ci95"][1])),
        })
    gaps = [r["gap"] for r in rows if r["gap"] is not None]
    return {
        "tier": tier,
        "n_scored": len(flags),
        "detectors_scoring": len(detectors),
        "rows": rows,
        # The two questions a sensitivity analysis exists to answer.
        "gap_sign_is_consistent": bool(gaps) and (all(g > 0 for g in gaps) or all(g < 0 for g in gaps)),
        "any_cut_separates": any(r["intervals_overlap"] is False for r in rows),
    }


def probe_by_distance(texts: list[str], tier: str = "lite", quantile: float = 0.2) -> dict:
    """False-positive rate for the most distant `quantile` of a corpus, against the rest.

    Returns ``None`` for the comparison rather than a number when either side is too small to say
    anything — the same refusal `untell/calibrate.py` makes. A disparity claim from four documents
    would be the kind of finding this repository exists to argue against.
    """
    if not 0 < quantile < 0.5:
        raise ValueError(f"quantile must be in (0, 0.5), got {quantile}")
    if len(texts) < 10:
        return {"n": len(texts), "error": "need at least 10 texts to split a corpus into margins"}

    distances, flags, detectors_seen, _ = _score_all(texts, tier)
    margin, centre, cut = _split(distances, flags, quantile)
    comparable = margin["n"] >= 5 and centre["n"] >= 5
    gap = None
    if comparable and margin["fpr"] is not None and centre["fpr"] is not None:
        gap = round(margin["fpr"] - centre["fpr"], 4)
    return {
        "tier": tier,
        "quantile": quantile,
        "detectors_scoring": len(detectors_seen),
        "distance_cut": round(cut, 4),
        "margin": margin,
        "centre": centre,
        "gap": gap,
        # The intervals decide whether a gap means anything, and on the corpus sizes this runs at
        # they usually overlap. Saying so is the whole discipline of this repo applied to its own
        # newest number.
        "intervals_overlap": (
            None if not comparable
            else not (margin["ci95"][0] > centre["ci95"][1] or centre["ci95"][0] > margin["ci95"][1])
        ),
        "note": (
            "Outlier status is NOT a protected attribute and this says nothing about which "
            "attribute drives any gap. On pre-LLM text every flag is a false positive by "
            "construction, so a gap is a real disparity in false accusations between writers far "
            "from the corpus norm and writers near it."
        ),
    }


def _render_sweep(report: dict) -> str:
    if "error" in report:
        return f"cannot run: {report['error']}"
    lines = [
        f"Sensitivity of the margin gap to where the line is drawn "
        f"(tier={report['tier']}, n={report['n_scored']}).",
        "",
        f"{'furthest':>9} {'margin n':>9} {'margin':>8} {'centre':>8} {'gap':>8}  separates?",
    ]
    for row in report["rows"]:
        if row["gap"] is None:
            lines.append(f"{row['quantile']:>8.0%} {row['margin']['n']:>9}      too few to compare")
            continue
        lines.append(
            f"{row['quantile']:>8.0%} {row['margin']['n']:>9} {row['margin']['fpr']:>7.1%} "
            f"{row['centre']['fpr']:>7.1%} {row['gap']:>+7.1%}  "
            f"{'no' if row['intervals_overlap'] else 'YES'}"
        )
    lines += [""]
    lines.append(
        "The gap keeps its sign at every cut-off."
        if report["gap_sign_is_consistent"]
        else "The gap CHANGES SIGN across cut-offs — the single-quantile headline is a choice, "
             "not a finding."
    )
    lines.append(
        "At least one cut-off separates the intervals."
        if report["any_cut_separates"]
        else "No cut-off separates the intervals, so none of these gaps is evidence of a disparity."
    )
    return "\n".join(lines)


# Word-count bands for the length control. A margin selected on stylometry is NOT length-balanced:
# MEASURED on 2,000 pre-LLM abstracts, the furthest 20% has a median of 124 words against 149 for the
# centre, and removing `words` from the feature set barely changes that (132 against 148) because
# type-token ratio and sentence-length variation are themselves length-dependent. Since this repo has
# already measured detectors flagging short text far more often, an unstratified margin gap is
# partly — possibly entirely — the length effect wearing a fairness costume.
STRATA: tuple[tuple[int, int], ...] = ((60, 100), (100, 150), (150, 220), (220, 10**9))


def probe_stratified(texts: list[str], tier: str = "lite", quantile: float = 0.2) -> dict:
    """The margin-versus-centre comparison run separately inside each word-count band.

    This is the control that decides whether an unstratified gap means anything. If the gap survives
    within bands, length is not driving it; if it changes sign or vanishes, the headline was
    measuring document length and calling it a disparity.
    """
    _distances, flags, detectors, kept = _score_all(texts, tier)
    scored = [(text, len(text.split()), flag) for text, flag in zip(kept, flags)]

    bands = []
    for low, high in STRATA:
        group = [(t, f) for t, w, f in scored if low <= w < high]
        if len(group) < 40:
            bands.append({"band": f"{low}-{'+' if high > 10 ** 8 else high}",
                          "n": len(group), "skipped": "fewer than 40 documents"})
            continue
        dist = outlier_scores([t for t, _ in group])
        margin, centre, _ = _split(dist, [f for _, f in group], quantile)
        # `_split` needs the flags ordered with the distances, which they are.
        comparable = margin["n"] >= 5 and centre["n"] >= 5
        bands.append({
            "band": f"{low}-{'+' if high > 10 ** 8 else high}",
            "margin": margin, "centre": centre,
            "gap": (round(margin["fpr"] - centre["fpr"], 4)
                    if comparable and None not in (margin["fpr"], centre["fpr"]) else None),
            "intervals_overlap": (
                None if not comparable
                else not (margin["ci95"][0] > centre["ci95"][1]
                          or centre["ci95"][0] > margin["ci95"][1])),
        })
    gaps = [b["gap"] for b in bands if b.get("gap") is not None]
    return {
        "tier": tier,
        "quantile": quantile,
        "n_scored": len(scored),
        "detectors_scoring": len(detectors),
        "bands": bands,
        "gap_sign_is_consistent": bool(gaps) and (all(g > 0 for g in gaps) or all(g < 0 for g in gaps)),
        "bands_separating": sum(1 for b in bands if b.get("intervals_overlap") is False),
        "note": (
            "Within-band comparison. An unstratified margin gap is confounded with document length, "
            "because the stylometric margin skews short and short text is flagged more often. If the "
            "gap does not survive here, the unstratified figure was measuring length."
        ),
    }


def _render_stratified(report: dict) -> str:
    lines = [
        f"Margin gap within word-count bands (tier={report['tier']}, "
        f"margin = furthest {report['quantile']:.0%}, n={report['n_scored']}).",
        "",
        f"{'band':<10} {'margin n':>9} {'margin':>8} {'centre':>8} {'gap':>8}  separates?",
    ]
    for b in report["bands"]:
        if "skipped" in b:
            lines.append(f"{b['band']:<10} {b['n']:>9}   {b['skipped']}")
            continue
        if b["gap"] is None:
            lines.append(f"{b['band']:<10} {b['margin']['n']:>9}   too few to compare")
            continue
        lines.append(
            f"{b['band']:<10} {b['margin']['n']:>9} {b['margin']['fpr']:>7.1%} "
            f"{b['centre']['fpr']:>7.1%} {b['gap']:>+7.1%}  "
            f"{'no' if b['intervals_overlap'] else 'YES'}")
    lines += ["", (
        "The gap keeps its sign in every band."
        if report["gap_sign_is_consistent"]
        else "The gap CHANGES SIGN between bands — once length is held roughly constant the effect "
             "does not hold, so an unstratified figure is measuring length.")]
    lines.append(f"{report['bands_separating']} band(s) separate their intervals.")
    lines += ["", report["note"]]
    return "\n".join(lines)


def _render(report: dict) -> str:
    if "error" in report:
        return f"cannot run: {report['error']}"
    lines = [
        f"False positives by distance from the corpus norm (tier={report['tier']}, "
        f"margin = furthest {report['quantile']:.0%}).",
        "",
        f"{'group':<10} {'n':>5} {'FPR':>8}   95% CI",
    ]
    for name in ("margin", "centre"):
        row = report[name]
        if row["fpr"] is None:
            lines.append(f"{name:<10} {row['n']:>5}        —")
            continue
        ci = f"[{row['ci95'][0]:.1%}, {row['ci95'][1]:.1%}]"
        lines.append(f"{name:<10} {row['n']:>5} {row['fpr']:>7.1%}   {ci}")
    if report["gap"] is None:
        lines += ["", "Too few documents on one side to compare."]
    else:
        lines += ["", f"gap: {report['gap']:+.1%}"]
        lines.append(
            "The intervals OVERLAP, so this gap is not evidence of a disparity."
            if report["intervals_overlap"]
            else "The intervals do NOT overlap."
        )
    if report["detectors_scoring"] < 2:
        lines += ["", "NOTE: one detector scored; this is that detector's disparity, not an "
                      "ensemble's."]
    lines += ["", report["note"]]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--cache", type=Path, default=Path(".anthology-cache"))
    parser.add_argument("--tier", default="lite")
    parser.add_argument("--limit", type=int, default=120)
    parser.add_argument("--quantile", type=float, default=0.2)
    parser.add_argument("--by-length", action="store_true",
                        help="run the comparison inside word-count bands — the control for the "
                             "length confound, and the one that decides whether a gap is real")
    parser.add_argument("--sweep", action="store_true",
                        help="report the gap at every margin cut-off instead of one")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    texts = pre_llm_abstracts(args.cache)[: args.limit]
    if not texts:
        print(f"no pre-LLM abstracts in {args.cache} — run "
              f"`python -m eval.litreview --download` first", file=sys.stderr)
        return 1
    if args.by_length:
        report = probe_stratified(texts, tier=args.tier, quantile=args.quantile)
        print(json.dumps(report, indent=2) if args.as_json else _render_stratified(report))
        return 0
    if args.sweep:
        report = probe_sweep(texts, tier=args.tier)
        print(json.dumps(report, indent=2) if args.as_json else _render_sweep(report))
        return 0
    report = probe_by_distance(texts, tier=args.tier, quantile=args.quantile)
    print(json.dumps(report, indent=2) if args.as_json else _render(report))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
