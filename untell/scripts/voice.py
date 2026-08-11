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

So the lever is real, but it is mostly **structural, not lexical**. Splitting and merging
sentences and repunctuating is what the free rewriters do; they do not change person or contract
words. The first three features and ``mean_word_len`` are used for matching, and the rest are
reported for the human to act on. A matcher that claimed to fit your contraction habit or your
first-person rate would be a placebo — there is nothing behind it to select over.

``mean_word_len`` moves least of the four (8% here, 0.103 between-author units per rewrite) and
carries most of the discrimination: without it the other three separate same-author from
cross-register text at AUROC 0.554, which is chance. The table above measures how much the rewriter
MOVES a feature; it does not measure whether the feature distinguishes anything, and those turned
out to be nearly opposite orderings. See the note on ``MATCHABLE``.

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
# IGNORECASE, which the line above already has and this one was missing. Without it "We", "My",
# "Our", "Me" and "Us" go uncounted — and sentence-initial is exactly where a first-person pronoun
# appears most, especially in the register this feature is meant to distinguish ("We propose…",
# "My experience was…"). MEASURED across 120 documents per corpus: 13% of first-person pronouns
# missed on HC3 and 50% on RAID, whose abstracts open sentence after sentence with "We".
# "I" is unaffected, being capitalised either way, which is what let this survive — the pronoun
# most people check with is the one case cannot break.
#
# SWEPT for siblings, over every compiled pattern in the package rather than by grep: patterns that
# lack IGNORECASE, list three or more lowercase words, and alternate between them. Six turned up and
# all six are correct. `browser_check`'s `_AI_LABEL`/`_HUMAN_LABEL` match against text that is
# `.lower()`ed first; `latex`'s `_NON_PROSE_ENV`/`_KEEP_ARG` match LaTeX commands, where case IS
# meaningful; `audit`'s `_ATTRIBUTION` spells its variants out by hand; `structural`'s `_ASIDE_RE`
# only ever matches after a comma. This was the only one.
_FIRST_PERSON = re.compile(r"\b(?:I|we|my|our|me|us)\b", re.IGNORECASE)

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
#
# `mean_word_len` was excluded on that rule and is now included, because it fails the rule's own
# premise. A feature nothing can change contributes the SAME value to every candidate's distance and
# therefore cannot move the ranking at all. MEASURED over 30 documents with four draws each, adding
# it changes which candidate wins in 6 of them — so the candidates do differ on it, and the
# rewriter's synonym pass is what moves them ("utilize" -> "use" shortens words directly). Its
# movement is 0.103 between-author units per rewrite against 0.243-0.331 for the three above: the
# weakest of the four, not zero.
#
# What it buys is most of the signal. Discriminating same-author text (halves of one HC3 answer)
# from different-register text (an HC3 answer against a RAID abstract), by AUROC:
#
#     sent_len + burst + comma_per_100w      0.554   <- chance
#     mean_word_len alone                    0.981
#     the four together                      0.880
#
# The three shipped features were not telling voices apart at all. Adding contractions instead was
# tried first and makes it worse (0.530): the obvious candidate is not the one that works.
#
# `first_person_per_100w` stays out and the rule stays right for it — 0.001 units of movement, which
# really is nothing, and changing how often an author says "I" is a content edit rather than a style
# one. Voice remains a tie-break applied after tells, so none of this can displace the primary
# objective; on the 6 documents whose pick changed, the new pick also carried one fewer tell.
MATCHABLE = ("sent_len", "burst", "comma_per_100w", "mean_word_len")

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


_WARNED_THIN_SAMPLE = False


def _warn_if_sample_is_thin(sample: str) -> None:
    """Say once when the sample is too small for the distance to mean much.

    `voice_report` already carries this as a `warning` key. `voice_distance` returns a bare float,
    so a library caller got a confident number and no caveat — MEASURED, a 9-word sample against
    the documented 150-word minimum returned 2.6543 in silence. The loop guards it separately
    (`untell humanize --voice-sample` warns on stderr), so this closes the direct-call path.

    Same shape as the `humanness` fix: the rich function reports the limit, the scalar one drops
    it, and the scalar one is what most callers reach for.
    """
    global _WARNED_THIN_SAMPLE
    if _WARNED_THIN_SAMPLE or len(_WORD.findall(sample)) >= MIN_SAMPLE_WORDS:
        return
    _WARNED_THIN_SAMPLE = True
    logger.warning(
        "the voice sample is under %d words, which is where the same-author/cross-author AUROC "
        "of 0.680 was measured; below it the distance is closer to noise than to a profile. "
        "Use voice_report() for the full picture.",
        MIN_SAMPLE_WORDS,
    )


def voice_distance(sample: str, draft: str) -> float:
    """One number: how far ``draft`` sits from ``sample``'s voice, over the matchable features.

    Root-mean-square rather than a sum, so one badly-wrong feature is not hidden by two right ones,
    and the result stays on the same "between-author gaps" scale as the per-feature numbers.
    """
    _warn_if_sample_is_thin(sample)
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
