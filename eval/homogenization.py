"""False-positive rate as a function of stylistic distance from the machine centre of mass.

**The gap this closes is one this repo wrote down and nobody in the literature has filled.**
`ai-writing-research.md`, *Gaps worth noting* #5:

    Homogenization and detection are not studied together, despite being two views of one
    phenomenon. A study measuring FPR as a function of a writer's distance from the model's
    stylistic centre of mass would connect §2 and §4 directly, and would explain the L2 result
    mechanistically rather than by correlation.

§2 is what LLMs do to writing — they compress it toward a centre. §4 is fairness: detectors flag
non-native and atypical writers more often. The literature treats these as separate findings and
connects them by correlation. If they are one phenomenon, the connection is mechanical and
measurable: **a detector's false-positive rate should fall as a document moves away from the
machine centroid**, and the L2 penalty is then not a bias about writers at all but the same
distance effect read from the other end — non-native prose sits closer to the centre because
that is where a model trained to be unremarkable also sits.

That is a prediction, and this module tests it.

WHAT MAKES THE TEST CLEAN. The corpus is `eval/pre_llm_fpr`'s: ACL Anthology abstracts from
volumes through 2021, which predate ChatGPT. **Text published before the model existed cannot
contain its output, so every flag is a false positive by construction** — no labelling, no
annotator agreement, nothing to dispute. 6,811 documents.

THE INSTRUMENT is Burrows's Delta, the standard stylometric distance, and it is chosen because it
is *already* a distance-from-a-centre-of-mass measure rather than because it is convenient. Relative
frequencies of the most frequent words, z-scored against the human corpus, mean absolute difference
from the machine centroid. Function words carry register and authorship and almost no topic, which
is what keeps this from measuring "abstracts about parsing" against "abstracts about translation".

⚠️ **LENGTH IS THE CONFOUND THAT COULD FAKE THIS ENTIRE RESULT, and it is not hypothetical.** This
repo has separately measured the same corpus at **28.69%** flagged for 60-100 word documents
against **12.77%** above 200. If distance to the centroid correlates with length — and it does,
because a short document estimates its own word frequencies badly and therefore lands further from
any centroid by noise alone — then a raw FPR-versus-distance curve measures length wearing a
costume. Every headline number here is therefore **directly standardized across the word-count
bands** `eval/pre_llm_fpr` already defines, and the crude figure is reported beside it so the size
of the confound is visible rather than absorbed.

WHAT IT MEANS FOR REMOVAL, which is the other half of what this repo is for. If FPR falls with
distance, then "removing AI tells" has a mechanical definition at last: **move the document away
from the centroid**. That is measurable per rewrite, it does not depend on the tell catalogue —
which rounds eighty-one and eighty-two showed reads register rather than authorship — and it gives
the rewriter an objective that is not the detector's own score. `rewrite_displacement` measures
whether the shipped rewriters actually do it.

    python -m eval.homogenization --n 800            # the curve, standardized
    python -m eval.homogenization --all --json
    python -m eval.homogenization --displacement     # do the rewriters move a document?
"""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
_WORD = re.compile(r"[A-Za-z']+")

# Burrows's Delta is conventionally computed over the most frequent 100-300 words. 150 is inside
# that band and is not tuned: `--vocab` moves it, and `vocab_sensitivity` reports the headline at
# 50/100/150/300 so a reader can see the answer does not depend on the choice.
DEFAULT_VOCAB = 150

# Distance quintiles rather than fixed cut-offs. The Delta scale has no natural units — it is
# z-scores averaged — so a fixed boundary would be a number nobody chose, which is the defect
# rounds eighty-six and eighty-nine of the ledger exist to prevent. Quintiles are defined by the
# data and give equal n per bin, which keeps the Wilson intervals comparable across bins.
N_BINS = 5


def _words(text: str) -> list[str]:
    return [w.lower() for w in _WORD.findall(text)]


def vocabulary(docs: list[str], size: int = DEFAULT_VOCAB) -> list[str]:
    """The most frequent words across the pooled corpus — Delta's feature set.

    Pooled over BOTH populations deliberately. Taking the vocabulary from the machine side alone
    would pick the features that side happens to use and guarantee the humans look distant; taking
    it from the human side alone does the reverse. The pooled list is the only choice that does not
    decide the answer before measuring it.
    """
    counts: Counter[str] = Counter()
    for doc in docs:
        counts.update(_words(doc))
    return [word for word, _ in counts.most_common(size)]


def profile(text: str, vocab: list[str]) -> list[float]:
    """Relative frequency of each vocabulary word in one document."""
    words = _words(text)
    if not words:
        return [0.0] * len(vocab)
    counts = Counter(words)
    total = len(words)
    return [counts[w] / total for w in vocab]


def centroid(profiles: list[list[float]]) -> list[float]:
    """The mean profile — the stylistic centre of mass."""
    if not profiles:
        raise ValueError("no profiles to average")
    width = len(profiles[0])
    return [statistics.fmean(p[i] for p in profiles) for i in range(width)]


def delta(target: list[float], centre: list[float],
          means: list[float], stdevs: list[float]) -> float:
    """Burrows's Delta: mean absolute z-score difference between a document and a centre.

    z-scored against the HUMAN corpus, which is the reference population whose false-positive rate
    is being explained. Standardizing against the pooled corpus instead would let the machine
    documents move the scale they are being measured on.
    """
    total = 0.0
    for value, centre_value, mean, stdev in zip(target, centre, means, stdevs):
        if stdev == 0:
            continue
        total += abs((value - mean) / stdev - (centre_value - mean) / stdev)
    return total / len(target) if target else 0.0


def distances(human: list[str], machine: list[str], size: int = DEFAULT_VOCAB) -> list[float]:
    """Each human document's Burrows's Delta to the machine centroid."""
    vocab = vocabulary(human + machine, size)
    human_profiles = [profile(t, vocab) for t in human]
    machine_profiles = [profile(t, vocab) for t in machine]
    centre = centroid(machine_profiles)
    means = [statistics.fmean(p[i] for p in human_profiles) for i in range(len(vocab))]
    stdevs = [
        statistics.pstdev([p[i] for p in human_profiles]) for i in range(len(vocab))
    ]
    return [delta(p, centre, means, stdevs) for p in human_profiles]


def _quantile_edges(values: list[float], bins: int) -> list[float]:
    """Interior cut points that split `values` into `bins` equal-count groups."""
    ordered = sorted(values)
    return [ordered[len(ordered) * i // bins] for i in range(1, bins)]


def _bin_of(value: float, edges: list[float]) -> int:
    index = 0
    for edge in edges:
        if value >= edge:
            index += 1
    return index


def scored_rows(texts: list[str], deltas: list[float], tier: str = "lite") -> list[dict]:
    """One row per document: its distance, its word count, and whether it was flagged.

    Flagged uses the SAME rule `eval/pre_llm_fpr` publishes — a detector at or above the result's
    own `verdict_threshold` — so this curve and that repo's headline false-positive rates are the
    same quantity measured two ways, and disagreeing would be a finding.
    """
    from untell.scripts.score import score_text

    rows: list[dict] = []
    for text, distance in zip(texts, deltas):
        result = score_text(text, tier=tier)
        values = [v for v in result["detectors"].values() if isinstance(v, (int, float))]
        if not values:
            continue
        threshold = result["verdict_threshold"]
        rows.append({
            "delta": distance,
            "words": len(_WORD.findall(text)),
            "flagged": int(any(v >= threshold for v in values)),
            "max": max(values),
        })
    return rows


def sign_test(away: int, closer: int) -> float:
    """Two-sided exact sign test on the direction of displacement.

    The counts are close enough on the machine arm that eyeballing them would be guessing: 9 moved
    away against 17 closer LOOKS like a rewriter pulling the wrong way, and at n=26 it is what a
    fair coin does about one time in six. Ties (a document the rewriter left byte-identical, or
    moved by exactly zero) are excluded rather than split, which is the conservative convention —
    they carry no directional evidence and counting them would shrink the p-value for free.
    """
    moved = away + closer
    if moved == 0:
        return 1.0
    fewer = min(away, closer)
    tail = sum(math.comb(moved, k) for k in range(fewer + 1)) / (2 ** moved)
    return min(1.0, 2 * tail)


def _wilson(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    from eval.pre_llm_fpr import wilson_interval

    return wilson_interval(successes, total, z)


def curve(rows: list[dict], bins: int = N_BINS) -> dict:
    """Flag rate per distance bin, crude and length-standardized side by side.

    The crude rate is reported because hiding it would hide the size of the confound. The
    standardized rate is the one to read: it reweights every distance bin to ONE common word-count
    distribution — the whole corpus's — so each bin answers "what would this bin's false-positive
    rate be if its documents had the corpus's length mix". That is the arm rounds eighty-eight and
    onward use, and it is the difference between measuring distance and measuring length.
    """
    from eval.pre_llm_fpr import _band

    if not rows:
        return {"error": "no scored rows"}
    edges = _quantile_edges([r["delta"] for r in rows], bins)
    for row in rows:
        row["bin"] = _bin_of(row["delta"], edges)
        row["band"] = _band(row["words"])

    # The standard population: how the whole corpus is distributed across length bands.
    band_share: Counter[str] = Counter(r["band"] for r in rows)
    total_rows = len(rows)

    out_bins = []
    for index in range(bins):
        members = [r for r in rows if r["bin"] == index]
        if not members:
            continue
        flagged = sum(r["flagged"] for r in members)
        low, high = _wilson(flagged, len(members))
        # Direct standardization: this bin's rate WITHIN each band, reweighted by the band's share
        # of the whole corpus. Bands this bin has no documents in contribute nothing and their
        # weight is dropped from the denominator, so the figure stays a rate.
        weighted, weight_used = 0.0, 0.0
        for band, share in band_share.items():
            inside = [r for r in members if r["band"] == band]
            if not inside:
                continue
            weight = share / total_rows
            weighted += weight * (sum(r["flagged"] for r in inside) / len(inside))
            weight_used += weight
        # ⚠️ Direct standardization CANNOT separate perfectly confounded variables, and when it
        # cannot, the arithmetic still returns a number — one identical to the crude rate, wearing
        # the name of a corrected one. If a bin holds documents from a single length band, there is
        # no within-band contrast to reweight and the "standardized" figure is the crude figure.
        # Reporting it anyway is the failure this repo names most often: a value meaning "could not
        # measure" and a value meaning "measured, and it is this" are the same number and opposite
        # facts. So it is reported as None with the reason, and `bands` says how much of the
        # standard population the bin actually covers.
        bands_present = {r["band"] for r in members}
        standardizable = len(bands_present) > 1 and len(band_share) > 1
        out_bins.append({
            "bin": index,
            "n": len(members),
            "delta_range": [round(min(r["delta"] for r in members), 4),
                            round(max(r["delta"] for r in members), 4)],
            "mean_words": round(statistics.fmean(r["words"] for r in members), 1),
            "flagged": flagged,
            "fpr_crude": round(flagged / len(members), 4),
            "ci95": [round(low, 4), round(high, 4)],
            "fpr_standardized": (round(weighted / weight_used, 4)
                                 if standardizable and weight_used else None),
            "standardization": (None if standardizable else
                                "not possible: the bin spans one length band, so there is no "
                                "within-band contrast to reweight"),
            "bands": sorted(bands_present),
            "weight_covered": round(weight_used, 4),
            "mean_max": round(statistics.fmean(r["max"] for r in members), 4),
        })
    return {
        "n": total_rows,
        "bins": out_bins,
        "delta_edges": [round(e, 4) for e in edges],
        "band_share": {k: round(v / total_rows, 4) for k, v in sorted(band_share.items())},
    }


def vocab_sensitivity(human: list[str], machine: list[str], rows_tier: str = "lite",
                      sizes: tuple[int, ...] = (50, 100, 150, 300)) -> dict:
    """The headline at four vocabulary sizes, because 150 was a choice and choices get swept.

    Rounds eighty-six and eighty-nine of the ledger are both about a constant nobody picked
    deciding a published figure. Delta's vocabulary size is exactly such a constant. What is
    reported is the SPREAD of the effect across sizes: if the direction survives 50 through 300,
    the finding is about style rather than about 150.
    """
    out = {}
    for size in sizes:
        deltas = distances(human, machine, size)
        rows = scored_rows(human, deltas, rows_tier)
        result = curve(rows)
        bins = result.get("bins") or []
        if len(bins) < 2:
            out[size] = {"error": "too few bins"}
            continue
        out[size] = {
            "nearest_standardized": bins[0]["fpr_standardized"],
            "farthest_standardized": bins[-1]["fpr_standardized"],
            "drop": round((bins[0]["fpr_standardized"] or 0) - (bins[-1]["fpr_standardized"] or 0), 4),
            "nearest_crude": bins[0]["fpr_crude"],
            "farthest_crude": bins[-1]["fpr_crude"],
        }
    return out


def rewrite_displacement(reference: list[str], machine: list[str], rewriters: tuple[str, ...],
                         tier: str = "lite", size: int = DEFAULT_VOCAB,
                         subjects: list[str] | None = None) -> dict:
    """Does rewriting actually move a document away from the machine centroid?

    The payoff for the removal half of this repo. If false-positive rate falls with distance, then
    "remove the AI tells" finally has a mechanical definition — increase the distance — and it is
    one that does NOT route through the tell catalogue, which rounds eighty-one and eighty-two
    measured as a register detector (AUROC 1.0000) and an authorship detector (0.2697). A rewriter
    can be scored on displacement whether or not the document contains a catalogued tell, which is
    exactly the case `surgical` cannot act on at all.

    Reported as the change in Delta, signed: positive means the rewrite moved the document AWAY from
    the machine centre, which is the direction that lowers false-positive rate on the curve above.

    ``subjects`` is what gets rewritten; ``reference`` is only the population the z-scores are taken
    against, and stays the human corpus so the scale does not move between arms. **Both arms are
    worth running and they ask different questions.** Rewriting MACHINE text is the product's actual
    job — it should move away from the centre. Rewriting HUMAN text is the control, and the more
    revealing of the two: a rewriter that drags already-human prose toward the machine centre is
    homogenizing, and on the curve above that is the direction that RAISES its false-positive risk,
    whatever it does to the score of the detector in the loop.
    """
    from untell.rewriter import get_rewriter
    from untell.scripts.score import score_text

    vocab = vocabulary(reference + machine, size)
    machine_centre = centroid([profile(t, vocab) for t in machine])
    human_profiles = [profile(t, vocab) for t in reference]
    means = [statistics.fmean(p[i] for p in human_profiles) for i in range(len(vocab))]
    stdevs = [statistics.pstdev([p[i] for p in human_profiles]) for i in range(len(vocab))]
    texts = reference if subjects is None else subjects

    out: dict[str, dict] = {}
    for name in rewriters:
        rewriter = get_rewriter(name)
        if rewriter is None:
            out[name] = {"error": "not available here"}
            continue
        moved, changed, before_scores, after_scores = [], 0, [], []
        for text in texts:
            score = score_text(text, tier=tier)
            try:
                rewritten = rewriter.rewrite(text, score, 0.30)
            except Exception as exc:  # a rewriter that cannot run is reported, not swallowed
                out[name] = {"error": f"{type(exc).__name__}: {str(exc)[:120]}"}
                break
            changed += int(rewritten != text)
            before = delta(profile(text, vocab), machine_centre, means, stdevs)
            after = delta(profile(rewritten, vocab), machine_centre, means, stdevs)
            moved.append(after - before)
            before_scores.append(score["max"])
            after_scores.append(score_text(rewritten, tier=tier)["max"])
        else:
            out[name] = {
                "n": len(texts),
                "changed": changed,
                "mean_displacement": round(statistics.fmean(moved), 4) if moved else None,
                "moved_away": sum(1 for m in moved if m > 0),
                "moved_closer": sum(1 for m in moved if m < 0),
                "unmoved": sum(1 for m in moved if m == 0),
                "p_sign_test": round(sign_test(sum(1 for m in moved if m > 0),
                                               sum(1 for m in moved if m < 0)), 4),
                "mean_score_before": round(statistics.fmean(before_scores), 4),
                "mean_score_after": round(statistics.fmean(after_scores), 4),
            }
    return out


def _render(report: dict) -> str:
    bins = report.get("bins") or []
    if not bins:
        return "no bins to report"
    lines = [
        "False-positive rate by stylistic distance from the machine centre of mass.",
        f"{report['n']} pre-ChatGPT ACL abstracts — human by construction, so every flag is a "
        "false positive.",
        "",
        f"{'bin':>4}  {'n':>5}  {'delta':>14}  {'words':>6}  {'crude':>7}  {'95% CI':>16}  "
        f"{'standardized':>12}",
    ]
    for row in bins:
        low, high = row["ci95"]
        std = row["fpr_standardized"]
        std_text = f"{std:>11.1%}" if std is not None else f"{'n/a':>11}"
        lines.append(
            f"{row['bin']:>4}  {row['n']:>5}  "
            f"{row['delta_range'][0]:>6.3f}-{row['delta_range'][1]:<7.3f}  "
            f"{row['mean_words']:>6.0f}  {row['fpr_crude']:>7.1%}  "
            f"[{low:>6.1%},{high:>6.1%}]  {std_text}"
        )
    near, far = bins[0], bins[-1]
    if near["fpr_standardized"] is None or far["fpr_standardized"] is None:
        lines += ["", "standardized comparison unavailable: " +
                  (near["standardization"] or far["standardization"] or "one bin could not be "
                   "standardized")]
        return "\n".join(lines)
    drop = near["fpr_standardized"] - far["fpr_standardized"]
    lines += [
        "",
        f"nearest bin {near['fpr_standardized']:.1%} -> farthest {far['fpr_standardized']:.1%} "
        f"standardized, a drop of {drop:.1%}",
        f"crude: {near['fpr_crude']:.1%} -> {far['fpr_crude']:.1%}  "
        f"(mean words {near['mean_words']:.0f} vs {far['mean_words']:.0f} — the confound, in view)",
        "",
        "Standardized is the number to read: each bin reweighted to the whole corpus's word-count",
        "mix, because this corpus flags 28.69% of 60-100 word documents against 12.77% above 200,",
        "and short documents land further from any centroid by estimation noise alone.",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--n", type=int, default=800,
                        help="how many pre-LLM abstracts to score (default 800)")
    parser.add_argument("--all", action="store_true", help="score the whole corpus")
    parser.add_argument("--tier", default="lite")
    parser.add_argument("--vocab", type=int, default=DEFAULT_VOCAB)
    parser.add_argument("--bins", type=int, default=N_BINS)
    parser.add_argument("--cache", type=Path, default=REPO / ".anthology-cache")
    parser.add_argument("--sweep", action="store_true",
                        help="report the headline at four vocabulary sizes")
    parser.add_argument("--displacement", action="store_true",
                        help="measure whether the free rewriters move a document off the centroid")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    from eval.data.generated_abstracts import ABSTRACTS as MACHINE
    from eval.pre_llm_fpr import pre_llm_abstracts

    human = pre_llm_abstracts(args.cache)
    if not human:
        print("no pre-LLM corpus: run `python -m eval.pre_llm_fpr --download` first", file=sys.stderr)
        return 1
    if not args.all:
        human = human[: args.n]
    machine = list(MACHINE)

    if args.displacement:
        names = ("composite", "structural", "surgical", "targeted")
        report = {
            # The product's actual job: machine text, which should move AWAY from the centre.
            "machine_subjects": rewrite_displacement(
                human, machine, names, args.tier, args.vocab, subjects=machine[:40]),
            # The control, and the more revealing arm — see `rewrite_displacement`.
            "human_subjects": rewrite_displacement(
                human, machine, names, args.tier, args.vocab, subjects=human[:40]),
        }
        print(json.dumps(report, indent=2) if args.as_json else json.dumps(report, indent=2))
        return 0

    if args.sweep:
        report = vocab_sensitivity(human, machine, args.tier)
        print(json.dumps(report, indent=2) if args.as_json else "\n".join(
            f"vocab {size:>4}: {info}" for size, info in report.items()))
        return 0

    deltas = distances(human, machine, args.vocab)
    report = curve(scored_rows(human, deltas, args.tier), args.bins)
    report["tier"] = args.tier
    report["vocab"] = args.vocab
    report["machine_docs"] = len(machine)
    print(json.dumps(report, indent=2) if args.as_json else _render(report))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
