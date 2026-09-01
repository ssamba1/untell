"""One check every two-arm comparison in this repository has to pass before it means anything.

The same confound has now produced a wrong headline three times:

* **Round thirty-six.** The outlier fairness gap separated its intervals at five of seven cut-offs on
  6,810 documents — margin 23.1% against centre 18.6% — and vanished once compared inside word-count
  bands. The margin was selected on stylometry, and stylometry is not length-neutral.
* **Round thirty-seven.** The same question asked of the author-status arm. That one passed, at a
  worst median gap of 7.8%, but only because somebody checked.
* **Round fifty.** The Frankentext probe reported stitched text flagged at 1.7% against 17.6%, a −16
  point gap, computed against a comparison arm of **seventeen** documents that happened to be long
  enough. Matched at 130 words it is −0.7%.

The cause is always the same and it is measured in this repository: **short text is flagged far more
often — 30.0% at ≤50 words against 13.3% at 200+.** Any comparison of flag rates between two groups
inherits that unless the groups are length-matched, and remembering to check has failed three times
out of three.

So it is a function, and the comparisons call it rather than their authors recalling it.
"""

from __future__ import annotations

import statistics

# Below this the difference is far smaller than the range over which the flag rate has been measured
# to move, and above it a comparison is measuring composition. A judgement call, stated as one.
MATCHED_WITHIN = 0.15

# A rate from a handful of documents is not a rate. Round fifty's -16 point gap came from an arm of
# seventeen; this is the floor below which a comparison is refused rather than reported.
MIN_ARM = 30


def word_counts(texts: list[str]) -> list[int]:
    return [len(t.split()) for t in texts]


def length_match(arms: dict[str, list[str]]) -> dict:
    """Are these arms comparable on length, and are they big enough to compare at all?

    Takes the arms as `{name: texts}` so a caller cannot accidentally check one and report the
    other. Returns a verdict, never raises: a comparison that refuses to run is more useful than one
    that raises inside somebody's audit.
    """
    sizes = {name: len(texts) for name, texts in arms.items()}
    medians = {name: (statistics.median(word_counts(texts)) if texts else 0.0)
               for name, texts in arms.items()}
    present = [m for m in medians.values() if m]
    worst = ((max(present) - min(present)) / min(present)) if len(present) > 1 else 0.0
    too_small = sorted(name for name, n in sizes.items() if n < MIN_ARM)
    return {
        "sizes": sizes,
        "median_words": medians,
        "worst_relative_gap": round(worst, 4),
        "length_matched": worst < MATCHED_WITHIN and not too_small,
        "arms_too_small": too_small,
        "reason": (
            f"arm(s) below {MIN_ARM} documents: {', '.join(too_small)}" if too_small
            else f"median word counts differ by {worst:.1%}, over the {MATCHED_WITHIN:.0%} bar"
            if worst >= MATCHED_WITHIN else "arms are comparable on length and size"
        ),
        "note": (
            "Short text is flagged far more often (30.0% at <=50 words against 13.3% at 200+, "
            "MEASURED by `python -m eval.pre_llm_fpr --by-length`), so a length imbalance between "
            "arms reads as a difference in flag rate. See rounds 36, 37 and 50 of "
            "docs/research-verification.md."
        ),
    }


def render_length_match(verdict: dict) -> str:
    """One line for a report header, phrased so a reader cannot skip past a failure."""
    if verdict["length_matched"]:
        return (f"Length check: arms ARE comparable (worst median gap "
                f"{verdict['worst_relative_gap']:.1%}).")
    return f"WARNING: arms are NOT comparable — {verdict['reason']}. Any gap below may be length."
