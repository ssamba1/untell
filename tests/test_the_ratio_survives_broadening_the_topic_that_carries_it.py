"""Round 86 swept the survey's first filter. This is the second, and it is the one that could break.

The survey runs two regexes in series: `DETECTION` selects the corpus, and a topic pattern selects
a row within it. The false-positives row is four alternatives long and returns 13 papers, and that
number carries this project's entire strategy. If broadening it to every reasonable synonym found
sixty papers, the imbalance would be an artefact of a narrow pattern rather than a fact about the
literature — a far more serious failure than anything the window sweep could have found, because
here the count is small enough that a handful of missed papers changes the conclusion.

MEASURED over the 612 detection papers, across four broadenings that each still *mean* the topic:
false positives goes 13 → 16 → 16 → 17 → 21 while robustness goes 157 → 176 → 184. Over all twelve
combinations the ratio runs **7.5x to 14.2x** and never approaches parity.

Two things these tests pin that are easy to get backwards:

* **The shipped pattern is the most discriminating rung, not the most flattering one.** Its lift
  over the corpus background is 7.1 and every broadening lowers it. A filter tuned to produce a
  conclusion would look the other way round.
* **One rung takes the ratio to 1.3x and is not a refutation.** Adding `reliab|trustworth|
  consequence` matches 123 papers because those are near-background words — a `reliab` stem is in
  7.1% of *every* abstract in the Anthology. It stays in the table so that a reader who broadens the
  pattern themselves finds it already measured rather than thinking they have overturned something.
  `term_lift` is the instrument that separates the two cases, and it is tested here directly.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eval import litreview

REPO = Path(__file__).resolve().parent.parent
CACHE = REPO / ".anthology-cache"
SWEEP = json.loads((REPO / "eval" / "data" / "topic_sweep.json").read_text())
COUNTS = json.loads((REPO / "eval" / "data" / "survey_counts.json").read_text())

FP = "false positives/accusation"
ROB = "robustness/paraphrase"

needs_corpus = pytest.mark.skipif(
    not (CACHE.exists() and any(CACHE.glob("*.xml"))),
    reason="Anthology corpus not cached (run `python -m eval.litreview --download`)",
)


def _honest(topic: str) -> list[dict]:
    return [r for r in SWEEP["rungs"][topic] if r["honest"]]


def test_the_shipped_rung_is_the_pattern_the_survey_actually_uses():
    """A ladder whose first rung is not the shipped regex measures something else entirely."""
    for topic in (FP, ROB):
        shipped = SWEEP["rungs"][topic][0]
        assert shipped["rung"] == "shipped"
        assert shipped["papers"] == COUNTS["topics"][topic]
        assert litreview.TOPIC_LADDERS[topic][0][1] == litreview.TOPICS[topic].pattern, (
            f"the ladder's shipped rung for {topic} has drifted from TOPICS"
        )


def test_broadening_the_row_never_brings_the_ratio_near_parity():
    """The central claim, tested against the broadenings most likely to overturn it."""
    assert SWEEP["ratio_min"] > 5.0, "no honest broadening makes the imbalance small"
    assert SWEEP["ratio_max"] > SWEEP["ratio_min"], "the ladder must actually vary something"


def test_the_shipped_count_is_conservative_rather_than_selected():
    """If the shipped rung were the *smallest* possible, the row would be picked to flatter."""
    counts = [r["papers"] for r in _honest(FP)]
    assert counts[0] == min(counts), "shipped must be the low end — the survey understates this row"
    assert max(counts) <= 2 * counts[0], (
        "if broadening more than doubled the row, 13 would be an artefact of a narrow pattern "
        "and the published figure would need replacing rather than qualifying"
    )


def test_the_shipped_pattern_is_the_most_informative_rung_not_the_least():
    """Lift, not count, is what says whether a pattern is measuring a topic or measuring English."""
    lifts = [r["lift"] for r in _honest(FP)]
    assert lifts[0] == max(lifts), (
        "every broadening should spend discrimination to buy papers; if a broadening raised lift, "
        "the shipped pattern is missing something real rather than being conservative"
    )


def test_the_rung_that_breaks_the_ratio_is_kept_and_marked():
    """A reader who broadens the pattern will land here. It must already be measured."""
    dishonest = [r for r in SWEEP["rungs"][FP] if not r["honest"]]
    assert len(dishonest) == 1, "the failing rung is documentation; do not quietly delete it"
    bad = dishonest[0]
    assert bad["papers"] > 5 * SWEEP["rungs"][FP][0]["papers"], "it must look like a refutation"
    assert bad["lift"] < min(r["lift"] for r in _honest(FP)), (
        "and it must be distinguishable from the honest rungs by lift alone — that is the whole "
        "reason lift is reported"
    )
    assert bad["papers"] not in [r["papers"] for r in _honest(FP)]


@needs_corpus
def test_lift_tells_a_topic_term_from_a_background_word():
    """The instrument itself, on the two cases that motivated it."""
    papers = litreview.load_abstracts(CACHE)
    real = litreview.term_lift(papers, r"falsely (flag|accus)")
    background = litreview.term_lift(papers, r"reliab\w+")
    assert real["lift"] > 10, "a phrase that names the topic should be far above background"
    assert background["corpus_rate"] > 5.0, (
        "the point of the counter-example is that it is common everywhere"
    )
    assert background["lift"] < 3, "and that being common everywhere shows up as low lift"
    assert real["lift"] > background["lift"] * 5


@needs_corpus
def test_the_committed_topic_sweep_still_matches_what_the_code_computes():
    papers = litreview.load_abstracts(CACHE)
    assert litreview.topic_sensitivity(papers) == SWEEP
