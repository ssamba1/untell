"""The survey's headline ratio rests on one number nobody chose. Vary it and see what survives.

`DETECTION_WINDOW` is 40 characters. Round fifty-seven picked it because the proximity rule needed
*a* window and this one cut the noise rate; no measurement chose it, and every count in ROADMAP
section 7 and `docs/index.md` sits downstream of it. A parameter like that is exactly where a
survey's conclusion goes to hide.

Round eighty-six swept it from 0 to 400. These tests pin what the sweep found, because the finding
is stronger than "the number is fine":

* The windows **nest** — no paper is ever lost by widening — so the parameter is a recall dial and
  nothing here is a reshuffling artefact.
* The corpus size is very sensitive to it (343 to 768 papers) and the topic *shares* are not
  (4.3 points at most). Shares therefore travel with their window; the topic ordering never moves.
* The false-positives row **saturates at w=30 with 13 papers** and stays there through w=400, while
  192 further detection papers enter behind it. Buying recall at any price in precision recruits
  none of that literature. Robustness nearly doubles across the same sweep.

The consequence is that the objection "your filter is too strict to find the false-positive work"
is answerable with a measurement rather than a defence, and the ratio moves *against* the objection:
9.3x at the tightest window, 14.0x at the widest, 12.1x published.

The corpus is 99 MB and not committed, so the sweep is committed instead
(`eval/data/window_sweep.json`) and checked against the code whenever the corpus is present.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eval import litreview

REPO = Path(__file__).resolve().parent.parent
CACHE = REPO / ".anthology-cache"
SWEEP = json.loads((REPO / "eval" / "data" / "window_sweep.json").read_text())
COUNTS = json.loads((REPO / "eval" / "data" / "survey_counts.json").read_text())

needs_corpus = pytest.mark.skipif(
    not (CACHE.exists() and any(CACHE.glob("*.xml"))),
    reason="Anthology corpus not cached (run `python -m eval.litreview --download`)",
)


def _row(window: int) -> dict:
    return next(r for r in SWEEP["rows"] if r["window"] == window)


def test_the_default_window_is_the_one_the_published_counts_came_from():
    """If someone edits DETECTION_WINDOW, every published figure moves. Say so loudly."""
    assert litreview.DETECTION_WINDOW == 40
    assert _row(40)["detection_papers"] == COUNTS["detection_papers"]
    assert _row(40)["topics"] == COUNTS["topics"]


def test_the_refactored_pattern_is_the_pattern_that_was_published():
    """`detection_pattern()` replaced a literal regex. Byte-identical, or the counts are not ours."""
    assert litreview.DETECTION.pattern == litreview.detection_pattern(40).pattern
    assert "{0,40}" in litreview.DETECTION.pattern


def test_widening_the_window_never_drops_a_paper():
    """Nesting is what makes the sweep a recall dial rather than nine unrelated corpora."""
    assert SWEEP["nested"] is True
    assert set(SWEEP["papers_lost_when_widening"].values()) == {0}


def test_the_corpus_size_is_sensitive_to_the_window_and_the_shares_are_not():
    """The point of quoting shares rather than counts, measured rather than assumed."""
    sizes = [r["detection_papers"] for r in SWEEP["rows"]]
    assert max(sizes) / min(sizes) > 2.0, "if this stops being sensitive, the finding changed"
    assert SWEEP["largest_share_move"] <= 5.0


def test_the_topic_ordering_never_changes_across_the_sweep():
    """A share that moves 4 points is only harmless if it does not overtake anything."""
    orders = {
        tuple(sorted(r["topics"], key=lambda k: (-r["topics"][k], k)))
        for r in SWEEP["rows"]
    }
    top = {order[0] for order in orders}
    assert top == {"robustness/paraphrase"}, "the largest topic must not depend on the window"
    for order in orders:
        assert order.index("robustness/paraphrase") < order.index("false positives/accusation")
        assert order.index("multilingual/cross-lingual") < order.index("fairness/non-native bias")


def test_the_false_positive_literature_is_absent_not_filtered_out():
    """The round-86 finding: recall buys robustness papers and buys no false-positive papers."""
    fp = SWEEP["saturates"]["false positives/accusation"]
    assert fp["window"] <= litreview.DETECTION_WINDOW, (
        "false positives must saturate at or before the published window — otherwise the count "
        "is a recall artefact and the survey is measuring its own filter"
    )
    assert fp["papers_entering_after"] > 100, (
        "the claim is that many further papers enter and none is a false-positive paper; "
        "if few enter, the saturation is not evidence of anything"
    )
    robustness = SWEEP["saturates"]["robustness/paraphrase"]
    assert robustness["window"] > fp["window"], (
        "robustness must still be growing where false positives has stopped, or the saturation "
        "is a property of the sweep rather than of the literature"
    )
    counts = [r["topics"]["robustness/paraphrase"] for r in SWEEP["rows"]]
    assert max(counts) >= 2 * min(counts) - 5, "robustness roughly doubles across the sweep"


def test_the_ratio_never_inverts_and_never_favours_the_published_number():
    """The published 12.1x must not be the sweep's best case, or the window was chosen to flatter."""
    ratios = {
        r["window"]: r["topics"]["robustness/paraphrase"] / r["topics"]["false positives/accusation"]
        for r in SWEEP["rows"]
    }
    assert min(ratios.values()) > 5.0, "no window makes the imbalance small"
    published = ratios[litreview.DETECTION_WINDOW]
    assert min(ratios.values()) < published < max(ratios.values()), (
        "the published window is an interior point of the sweep, not its extreme"
    )


def test_the_documented_zero_on_disability_is_not_a_recall_artefact_either():
    """Round sixteen published a near-zero. A recall sweep is how you find out it was real."""
    sat = SWEEP["saturates"]["disability/neurodivergence"]
    assert sat["papers"] <= 2
    assert sat["papers_entering_after"] > 200


@needs_corpus
def test_the_committed_sweep_still_matches_what_the_code_computes():
    """The artefact is evidence only while it cannot drift from the corpus it claims to describe."""
    papers = litreview.load_abstracts(CACHE)
    fresh = litreview.window_sensitivity(papers)
    assert fresh["rows"] == SWEEP["rows"]
    assert fresh["saturates"] == SWEEP["saturates"]
    assert fresh["nested"] == SWEEP["nested"]
