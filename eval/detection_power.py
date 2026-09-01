"""Does this detector separate machine text from human text at all, at matched length?

Every false-positive measurement in this repository — 19.47% on pre-LLM abstracts, 28.69% at 60-100
words — answers half a question. A detector that flags nothing has no false positives, and one that
flags everything catches every machine document. **Neither number means anything without the other**,
and the other was unmeasurable here: HC3 and RAID both require network access this environment
denies.

`eval/data/generated_abstracts.py` supplies the missing arm. Its texts were written by a large
language model, so the label is provenance rather than annotation — the one property those corpora
buy with a download.

MEASURED at the shipped verdict threshold of 0.45, matched by length against pre-LLM ACL abstracts:

    band       machine                        human
    40-60       9.7%  [3.3%, 24.9%]  n=31     64.5%  [46.9%, 78.9%]  n=31
    60-100     12.0%  [4.2%, 30.0%]  n=25     28.7%  [25.2%, 32.4%]  n=603
    100+        7.1%  [1.3%, 31.5%]  n=14     18.6%  [17.6%, 19.6%]  n=6,207

    40-100     10.7%  [5.0%, 21.5%]  n=56     30.4%  [27.0%, 34.1%]  n=634

**In every band the detector flags human text more often than machine text**, and over the matched
40-100 range the intervals do not overlap. Mean score is 0.2962 for the machine arm against 0.3718
for the human one.

That is not a weak detector. On this register it is pointed the wrong way.

⚠️ **What this does and does not support.** One model's output, one register, n=56. The machine
abstracts were written across many topics and deliberately varied, which may make them more
sentence-length-varied than typical model output — and since the detector's largest term rewards
uniformity, that would bias the machine arm's score DOWN. So the true separation could be better
than this shows. It could not plausibly be reversed: the human arm is 634 real abstracts and its rate
is measured to within a few points.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from eval.pre_llm_fpr import wilson_interval

DEFAULT_THRESHOLD = 0.45
# Matched to the human corpus's own bands. Comparing arms of different lengths is the confound
# `eval/arms.py` exists for, and this detector's length effect is large enough to swamp any real
# signal if the arms are not matched.
BANDS: tuple[tuple[int, int], ...] = ((40, 60), (60, 100), (100, 10**9))


def ranking_auroc(machine: list[float], human: list[float]) -> float | None:
    """P(a random machine text scores above a random human one), ties counted as half.

    **The threshold-free summary, and the one that decides whether a detector works at all.** A flag
    rate is a property of the detector AND the bar; AUROC is a property of the ordering. 0.5 is a
    coin flip and below 0.5 means the detector ranks human text as more machine-like.

    MEASURED on the matched 40-100 range through `score_text`, which is what `--run` executes:
    **0.3529**, 95% bootstrap CI **[0.2822, 0.4270]** — the whole interval below 0.5.

    ⚠️ Round seventy-seven published **0.3538** for this. That figure is real and came from a
    reimplementation of the score's components, used to compare two burstiness estimators without
    re-running the whole pipeline. It is not what the shipped detector returns. Round eighty-four
    made the arc reproducible in one command, the command printed 0.3529, and the published number
    was corrected to it — **the reproduction command is the authority, not the script that found
    the result.** And it rises toward 0.5 with length: 0.1873 at 40-60 words, 0.3599 at
    60-100, 0.4589 at 100+, which is what the small-sample burstiness bias predicts, since longer
    documents have more sentences and less estimator bias.

    ✗ **This is what the flag rates could not tell us, and what they misled about.** Round
    seventy-six reported that `burstiness_bias_corrected` improved the machine-to-human flag ratio
    and read that as the correction helping. By AUROC it does not: **0.3538 -> 0.3402** on the
    matched range, marginally worse. Correcting the estimator lowers every score, so fewer documents
    of either class cross a fixed bar — an apparent gain at one threshold that is no gain in
    ordering. A paired flag-rate comparison at a fixed threshold cannot distinguish the two, and
    AUROC can.
    """
    if not machine or not human:
        return None
    wins = sum((m > h) + 0.5 * (m == h) for m in machine for h in human)
    return wins / (len(machine) * len(human))


def component_auroc(
    machine: list[dict], human: list[dict], keys: tuple[str, ...],
) -> dict[str, float | None]:
    """AUROC of each named component, to find which term inverts a detector — or that none does.

    Each entry is a mapping of component name to value for one document. Ranking each component on
    its own says whether the whole is dragged down by one term or is uniformly bad.

    MEASURED on the matched 40-100 range, machine against human:

        full score        0.3532
        burst_signal      0.4122
        common_signal     0.3459
        rep               0.5000

    ✗ **Both live components are below 0.5, and burstiness is the BETTER of them.** The hypothesis
    that motivated this — that burstiness is the bad term and dropping it would help — is refuted:
    scoring on `common_signal` alone gives 0.3459, worse than the full score.

    The common-word term is the more inverted, and the reason is legible. Academic abstracts are
    dense in function words and stock phrasing ("we show that", "in this paper"); machine abstracts
    written across seventy different topics carry more varied vocabulary. The feature reads genre,
    and in this corpus the genre is the human one.

    `rep` sits at exactly 0.5000 in every band, which is **correct and not a defect**. It is a
    degenerate-collapse guard with a type-token floor at 0.25, documented as being "exactly 0.0" on
    real text by construction. VERIFIED: it returns 1.0 on 100 repeated words and 0.0 on prose. A
    first probe of this reported it as never firing, because the probes were under the function's
    own 40-word minimum and hit the length guard rather than the ratio test.
    """
    out: dict[str, float | None] = {}
    for key in keys:
        out[key] = ranking_auroc([d[key] for d in machine if key in d],
                                 [d[key] for d in human if key in d])
    return out


def _rate(scores: list[float], threshold: float) -> dict:
    flagged = sum(s >= threshold for s in scores)
    low, high = wilson_interval(flagged, len(scores)) if scores else (0.0, 1.0)
    return {
        "n": len(scores),
        "flagged": flagged,
        "rate": round(flagged / len(scores), 4) if scores else None,
        "ci95": [round(low, 4), round(high, 4)],
    }


def compare(
    machine: list[tuple[int, float]], human: list[tuple[int, float]],
    threshold: float = DEFAULT_THRESHOLD,
) -> dict:
    """Flag rates for both arms, per matched length band and pooled over the overlapping range.

    ``machine`` and ``human`` are ``(word_count, score)`` pairs. Bands where either arm is empty are
    reported as ``None`` rather than dropped silently — a band present in one arm and not the other
    is exactly what an unmatched comparison hides.
    """
    bands: dict[str, dict] = {}
    pooled_machine: list[float] = []
    pooled_human: list[float] = []
    for low, high in BANDS:
        label = f"{low}-{high}" if high < 10**9 else f"{low}+"
        m = [s for words, s in machine if low <= words < high]
        h = [s for words, s in human if low <= words < high]
        bands[label] = {
            "machine": _rate(m, threshold) if m else None,
            "human": _rate(h, threshold) if h else None,
        }
        # Pool only where BOTH arms have data, which is what "matched" means.
        if m and h and high <= 100:
            pooled_machine += m
            pooled_human += h
    machine_pooled, human_pooled = _rate(pooled_machine, threshold), _rate(pooled_human, threshold)
    auroc = ranking_auroc(pooled_machine, pooled_human)
    separated = (
        bool(pooled_machine) and bool(pooled_human)
        and machine_pooled["ci95"][1] < human_pooled["ci95"][0]
    )
    return {
        "threshold": threshold,
        "bands": bands,
        "matched": {"machine": machine_pooled, "human": human_pooled},
        # Threshold-free. A flag rate can be moved by shifting every score; this cannot.
        "auroc": round(auroc, 4) if auroc is not None else None,
        # True when the machine arm is flagged LESS than the human one with non-overlapping
        # intervals: the detector is pointed the wrong way, not merely weak.
        "inverted": separated,
    }


def render(report: dict) -> str:
    lines = [
        f"Flag rates at threshold {report['threshold']}, matched by length.",
        "Every flag on the human arm is a false positive; every miss on the machine arm is a "
        "false negative.",
        "",
        f"{'band':<10} {'machine':>22}   {'human':>22}",
    ]
    for label, row in report["bands"].items():
        def cell(entry: dict | None) -> str:
            if not entry or entry["rate"] is None:
                return f"{'-':>22}"
            return (f"{entry['rate']:>7.1%} [{entry['ci95'][0]:.1%},{entry['ci95'][1]:.1%}]"
                    f" n={entry['n']}")
        lines.append(f"{label:<10} {cell(row['machine']):>22}   {cell(row['human']):>22}")
    matched = report["matched"]
    lines += ["", "matched range (both arms present):"]
    for arm in ("machine", "human"):
        entry = matched[arm]
        if entry["rate"] is not None:
            lines.append(f"  {arm:<8} {entry['flagged']}/{entry['n']} = {entry['rate']:.1%}  "
                         f"[{entry['ci95'][0]:.1%}, {entry['ci95'][1]:.1%}]")
    if report.get("auroc") is not None:
        lines += ["", f"AUROC {report['auroc']:.4f}  (0.5 = coin flip; below = human ranked as "
                      f"more machine-like)"]
    if report["inverted"]:
        lines += [
            "",
            "INVERTED: the machine arm is flagged LESS than the human arm, intervals not "
            "overlapping.",
            "On this register the detector is pointed the wrong way — not weak, reversed.",
        ]
    return "\n".join(lines)


def score_arm(texts, tier: str = "lite") -> list[tuple[int, float]]:
    """(word_count, detector score) for each text, skipping any the detector declines to score."""
    from untell.scripts.score import score_text

    out = []
    for text in texts:
        flat = " ".join(text.split())
        result = score_text(flat, tier=tier)
        values = [v for v in result.get("detectors", {}).values() if isinstance(v, (int, float))]
        if values:
            out.append((len(flat.split()), values[0]))
    return out


def human_arm(cache, min_words: int = 40, max_words: int = 100, limit: int | None = None,
              tier: str = "lite", seed: int = 0) -> list[tuple[int, float]]:
    """The known-human arm: pre-2022 ACL abstracts, in the length range the machine arm covers.

    Bounded above as well as below. The machine arm tops out around 220 words, and pooling a human
    arm that runs to 356 against it would compare length as much as authorship — see `eval/arms.py`.
    """
    import random

    from eval.pre_llm_fpr import pre_llm_abstracts

    texts = [t for t in pre_llm_abstracts(cache, min_words, 2021)
             if min_words <= len(t.split()) < max_words]
    random.Random(seed).shuffle(texts)
    return score_arm(texts[:limit] if limit else texts, tier=tier)


def register_comparison(tier: str = "lite") -> dict:
    """The same author in three registers, which is what separates register from authorship.

    Round eighty-two: the tell catalogue separates assistant-register prose from academic prose at
    AUROC 1.0000 with authorship held constant, and cannot separate its own two target registers
    from each other (0.5625). A detector that does that is reading register.
    """
    from eval.data.generated_abstracts import ABSTRACTS
    from eval.data.generated_registers import ASSISTANT, PROMOTIONAL
    from untell.scripts.tells import score_tells

    def density(texts, low, high):
        out = []
        for text in texts:
            flat = " ".join(text.split())
            if low <= len(flat.split()) < high:
                out.append(score_tells(flat)["tells_per_100w"])
        return out

    return {
        "tells_60_100": {
            "academic": density(ABSTRACTS, 60, 100),
            "assistant": density(ASSISTANT, 60, 100),
        },
        "tells_30_60": {
            "academic": density(ABSTRACTS, 30, 60),
            "promotional": density(PROMOTIONAL, 30, 60),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--machine", type=str, default=None,
                        help="JSON [[words, score], ...]; defaults to scoring the packaged corpus")
    parser.add_argument("--human", type=str, default=None,
                        help="JSON [[words, score], ...] from a known-human corpus")
    parser.add_argument("--run", action="store_true",
                        help="build and score both arms from scratch: the packaged machine corpus "
                             "and pre-2022 ACL abstracts from --cache. Needs the Anthology cache "
                             "(python -m eval.pre_llm_fpr --download)")
    parser.add_argument("--cache", type=Path, default=Path(".anthology-cache"))
    parser.add_argument("--limit", type=int, default=None,
                        help="cap the human arm, for a faster run")
    parser.add_argument("--registers", action="store_true",
                        help="also report the same-author register comparison (round eighty-two)")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    if args.machine:
        machine = [tuple(x) for x in json.loads(Path(args.machine).read_text())]
    else:
        from eval.data.generated_abstracts import ABSTRACTS

        machine = score_arm(ABSTRACTS)

    if args.human:
        human = [tuple(x) for x in json.loads(Path(args.human).read_text())]
    elif args.run:
        human = human_arm(args.cache, limit=args.limit)
        if not human:
            print(f"no pre-2022 abstracts in {args.cache} — run "
                  f"`python -m eval.pre_llm_fpr --download` first", file=sys.stderr)
            return 1
    else:
        print("give --human a scored corpus, or --run to build one from --cache", file=sys.stderr)
        return 2

    report = compare(machine, human, args.threshold)
    if args.registers:
        report["registers"] = {
            band: {arm: {"n": len(v), "mean_tells_per_100w": round(sum(v) / len(v), 4)}
                   for arm, v in arms.items() if v}
            for band, arms in register_comparison().items()
        }
        for band, arms in register_comparison().items():
            names = [k for k, v in arms.items() if v]
            if len(names) == 2:
                report["registers"][band]["auroc"] = round(
                    ranking_auroc(arms[names[1]], arms[names[0]]) or 0.0, 4)
    print(json.dumps(report, indent=2) if args.as_json else render(report))
    if args.registers and not args.as_json:
        print()
        print("same author, register against register (tells per 100 words):")
        for band, arms in report["registers"].items():
            parts = [f"{k} {v['mean_tells_per_100w']:.3f} (n={v['n']})"
                     for k, v in arms.items() if isinstance(v, dict)]
            auroc = arms.get("auroc")
            print(f"  {band}: " + "   ".join(parts)
                  + (f"   AUROC {auroc:.4f}" if auroc is not None else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
