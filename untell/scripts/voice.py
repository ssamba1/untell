"""Voice matching — how far a draft sits from the way *you* write.

The catalogue in ``tells.py`` answers "does this read like a machine". This answers a different
question: "does this read like ME". They are not the same axis. Text can be free of every
catalogued tell and still sound nothing like its supposed author, which is what gives a reader the
uneasy feeling that something was outsourced even when no single sentence is wrong.

    untell-voice --sample my-writing.txt --draft rewrite.txt
    untell-voice --sample my-writing.txt --draft rewrite.txt --json

WHAT THIS CAN AND CANNOT DO, measured rather than asserted. A voice matcher is only useful if the
rewriter can actually move the features it scores. Measured on 6 real HC3 texts, 8 composite draws
each, comparing the spread ACROSS DRAWS of one text against the spread BETWEEN different texts:

    feature                  within-draw sd / between-text sd
    burst                        163%    <- the rewriter varies this more than texts differ
    sent_len                     144%
    comma_per_100w                41%
    mean_word_len                  8%
    contractions_per_100w          3%
    first_person_per_100w          1%

So the lever is real, but it is **structural, not lexical**. Splitting and merging sentences and
repunctuating is what the free rewriters do; they do not change person, contract words, or reach
for longer ones. Only the first three features are therefore used for matching, and the rest are
reported for the human to act on. A matcher that claimed to fit your contraction habit or your
first-person rate would be a placebo — there is nothing behind it to select over.

The scale constants are the standard deviation of each feature across 150 real human texts, so a
distance of 1.0 in any feature means "one typical between-author gap". That makes the per-feature
numbers comparable and the total interpretable, instead of summing words against ratios.

HOW STRONG IS IT, on the hardest test available. Splitting real human texts in half gives pairs
that share an author, and pairing halves from different texts gives pairs that do not. Distance
should be smaller for the first kind. Measured on 270 halved HC3 texts:

    min sample words     same-author median   cross-author median   AUROC
        any                    0.842                1.030           0.611
        100                    0.714                0.933           0.642
        150                    0.667                0.939           0.680
        200                    0.632                0.881           0.689

Modest, and it is stated here rather than buried: at short lengths the feature noise rivals the
between-author signal, which is why ``MIN_SAMPLE_WORDS`` is 150 — the point where the same-author
median first drops clearly below the cross-author one. Two things make this a floor rather than a
verdict. HC3's human answers are a homogeneous population (forum answers on similar topics), so its
"different authors" are genuinely alike; and the shipped use is not telling two people apart but
measuring how far a rewrite drifted from one known sample, which is a far larger gap — a terse
first-person sample against an ornate subordinate-clause draft scores 4.02.

Do not read the distance as an identity claim. It is a drift gauge.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import statistics as st
import sys

if __package__ in (None, ""):
    from pathlib import Path as _Path

    for _p in _Path(__file__).resolve().parents:
        if (_p / "untell" / "__init__.py").exists():
            sys.path.insert(0, str(_p))
            break

logger = logging.getLogger(__name__)

_WORD = re.compile(r"[A-Za-z0-9']+")
_CONTRACTION = re.compile(r"\b\w+['’](?:s|t|re|ve|ll|d|m)\b", re.IGNORECASE)
_FIRST_PERSON = re.compile(r"\b(?:I|we|my|our|me|us)\b")

# Feature spread across 150 real human HC3 texts. One unit = one typical between-author gap.
_SCALE = {
    "sent_len": 9.0108,
    "burst": 0.1807,
    "comma_per_100w": 3.4984,
    "contractions_per_100w": 0.8589,
    "mean_word_len": 0.3963,
    "first_person_per_100w": 1.7830,
}

# The features a free rewriter can actually move (see the module docstring). Matching is scored on
# these alone; the others are reported but carry zero weight, because scoring a feature nothing can
# change would let a candidate win or lose on noise.
MATCHABLE = ("sent_len", "burst", "comma_per_100w")

# Calibrated, not guessed — see the table in the module docstring. Below 150 words the
# same-author and cross-author distance distributions overlap heavily, because sentence-length
# variance over a handful of sentences is dominated by which sentences happened to be included.
MIN_SAMPLE_WORDS = 150


def _sentences(text: str) -> list[str]:
    from untell.text_split import split_sentences

    return split_sentences(text)


def style_profile(text: str) -> dict[str, float]:
    """Six measurable habits of a writer. All rates are per 100 words so lengths are comparable."""
    words = _WORD.findall(text)
    n_words = len(words) or 1
    lengths = [len(_WORD.findall(s)) for s in _sentences(text)] or [0]
    mean_len = st.mean(lengths)
    return {
        "sent_len": round(mean_len, 4),
        # Coefficient of variation: the rhythm of long and short sentences, not their average.
        "burst": round(st.pstdev(lengths) / mean_len, 4) if mean_len else 0.0,
        "comma_per_100w": round(text.count(",") / n_words * 100, 4),
        "contractions_per_100w": round(len(_CONTRACTION.findall(text)) / n_words * 100, 4),
        "mean_word_len": round(st.mean([len(w) for w in words] or [0]), 4),
        "first_person_per_100w": round(len(_FIRST_PERSON.findall(text)) / n_words * 100, 4),
    }


def voice_gaps(sample: str, draft: str) -> dict[str, float]:
    """Per-feature distance in between-author units. Positive = the draft over-does the feature."""
    a, b = style_profile(sample), style_profile(draft)
    return {k: round((b[k] - a[k]) / _SCALE[k], 4) for k in _SCALE}


def voice_distance(sample: str, draft: str) -> float:
    """One number: how far ``draft`` sits from ``sample``'s voice, over the matchable features.

    Root-mean-square rather than a sum, so one badly-wrong feature is not hidden by two right ones,
    and the result stays on the same "between-author gaps" scale as the per-feature numbers.
    """
    gaps = voice_gaps(sample, draft)
    return round((sum(gaps[k] ** 2 for k in MATCHABLE) / len(MATCHABLE)) ** 0.5, 4)


def voice_report(sample: str, draft: str) -> dict:
    """Full comparison, including the advisory features the loop cannot act on."""
    sample_words = len(_WORD.findall(sample))
    report = {
        "distance": voice_distance(sample, draft),
        "matched_on": list(MATCHABLE),
        "sample": style_profile(sample),
        "draft": style_profile(draft),
        "gaps": voice_gaps(sample, draft),
        "sample_words": sample_words,
    }
    if sample_words < MIN_SAMPLE_WORDS:
        report["warning"] = (
            f"sample is {sample_words} words; below {MIN_SAMPLE_WORDS} the profile is dominated by "
            f"which sentences happened to be included, so treat the distance as indicative only"
        )
        logger.warning(report["warning"])
    return report


def _describe(gap: float, feature: str) -> str:
    if abs(gap) < 0.25:
        return "matches"
    direction = {
        "sent_len": ("shorter sentences", "longer sentences"),
        "burst": ("more uniform rhythm", "more varied rhythm"),
        "comma_per_100w": ("fewer commas", "more commas"),
        "contractions_per_100w": ("fewer contractions", "more contractions"),
        "mean_word_len": ("shorter words", "longer words"),
        "first_person_per_100w": ("less first person", "more first person"),
    }[feature]
    return f"draft uses {direction[gap > 0]} ({gap:+.2f})"


def main(argv: list[str] | None = None) -> int:
    """CLI: compare a draft against a writing sample. Exit 0 always — this is a report, not a gate."""
    from untell.scripts.io_utils import configure_utf8_io

    configure_utf8_io()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    p = argparse.ArgumentParser(
        prog="untell-voice",
        description="How far a draft sits from the way you write.",
        epilog="Matching is scored on sentence length, rhythm and comma rate — the features a free "
        "rewriter can actually move. The rest are reported for you to act on.",
    )
    p.add_argument("--sample", required=True, help="file of YOUR writing (120+ words)")
    p.add_argument("--draft", required=True, help="file containing the draft to compare")
    p.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    args = p.parse_args(argv if argv is not None else sys.argv[1:])

    # read_file, not open(): a writing sample is most likely to arrive as the .docx or .pdf the
    # author actually writes in, and it already rejects binaries with a clear message.
    from untell.scripts.io_utils import read_file_or_exit

    sample, draft = read_file_or_exit(args.sample), read_file_or_exit(args.draft)
    report = voice_report(sample, draft)
    if args.json:
        print(json.dumps(report, ensure_ascii=True, indent=2))
        return 0

    print(f"voice distance: {report['distance']:.3f} (0 = same voice, 1 = a typical author apart)")
    print(f"  matched on: {', '.join(MATCHABLE)}\n")
    print(f"  {'feature':24} {'yours':>9} {'draft':>9} {'gap':>7}   reading")
    for k in _SCALE:
        mark = " " if k in MATCHABLE else "."
        print(
            f" {mark}{k:24} {report['sample'][k]:9.2f} {report['draft'][k]:9.2f} "
            f"{report['gaps'][k]:+7.2f}   {_describe(report['gaps'][k], k)}"
        )
    print("\n  (. = reported only; the rewriter cannot move it, so it is not scored)")
    if "warning" in report:
        print(f"\n  WARNING: {report['warning']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
