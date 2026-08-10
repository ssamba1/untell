"""The tells catalogue's headline separation must be re-derivable, not hand-maintained.

The detector ensemble has `eval/detector_audit.py`. The catalogue had nothing equivalent: its
overall AUROC lived in a comment, was computed by hand, and drifted. It read 0.638 on RAID while
the shipped catalogue scored 0.9555 — the two repetition tells landed after the number was written,
and because nothing re-derived it, the comment kept asserting the old value while the table
directly below it was updated with the new categories.

That is a class of failure a test can prevent, so these pin the harness rather than the number: the
metric's direction, its layout control, and the property that made the drift diagnosable (excluding
a category reproduces the figure from before it existed).

The corpus-backed figures themselves are network-dependent and slow, so they stay in the comment
and are reproduced with `python -m eval.tells_auroc --dataset raid --pairs 200`.
"""

from __future__ import annotations

import pytest

from eval.tells_auroc import LAYOUT_CATEGORIES, auroc, collapse_layout, measure, render

# Enough tells to score, and plain prose that scores near zero.
_AI = (
    "Moreover, we leverage robust and seamless solutions. Furthermore, this is a testament to "
    "the evolving landscape. It is not just a tool, it is a philosophy. Great question! I hope "
    "this helps with your work."
)
_HUMAN = (
    "The kettle boiled while I read the last few pages. Rain had started again, and the window "
    "fogged at the corners. I put the book down and went to look for a dry coat."
)


class TestAuroc:
    def test_perfect_separation(self) -> None:
        assert auroc([1.0, 2.0], [0.1, 0.2]) == 1.0

    def test_inversion(self) -> None:
        assert auroc([0.1, 0.2], [1.0, 2.0]) == 0.0

    def test_ties_count_as_half(self) -> None:
        assert auroc([1.0], [1.0]) == 0.5

    @pytest.mark.parametrize("ai,human", [([], []), ([1.0], []), ([], [1.0])])
    def test_empty_returns_none(self, ai, human) -> None:
        assert auroc(ai, human) is None


class TestMeasure:
    def test_ai_text_scores_above_human_text(self) -> None:
        """Direction check: the metric would be silently useless inverted."""
        m = measure([(_HUMAN, _AI)] * 5)
        assert m["ai_mean"] > m["human_mean"]
        assert m["gap"] > 0
        assert m["auroc"] == 1.0

    def test_reports_the_layout_control_every_run(self) -> None:
        """The delta must always be present, so a corpus that starts depending on layout shows up."""
        m = measure([(_HUMAN, _AI)] * 3)
        for key in ("auroc_layout_collapsed", "layout_delta", "auroc_without_layout_categories"):
            assert key in m

    def test_layout_is_not_collapsed_in_the_headline_figure(self) -> None:
        """Deliberately unlike detector_audit: three categories are line-anchored by design.

        A markdown artifact must still count as a tell, so the reported AUROC is over text as
        supplied. Collapsing is measured alongside, never applied.
        """
        formatted = "## Key Takeaways\n\nThe method is fast and the results are reproducible.\n"
        m = measure([(_HUMAN, formatted)] * 4)
        assert m["layout_categories_fire_on"] > 0
        # Silencing the tell changes the answer -- which is why it is reported, not removed.
        assert m["auroc_layout_collapsed"] != m["auroc"] or m["auroc_without_layout_categories"] != m["auroc"]

    def test_counts_documents_not_pairs(self) -> None:
        m = measure([(_HUMAN, _AI)] * 7)
        assert m["n_pairs"] == 7
        assert m["documents"] == 14


class TestRender:
    def test_flags_a_corpus_whose_layout_moves_the_metric(self) -> None:
        m = measure([(_HUMAN, "## Key Takeaways\n\nFast, reproducible results here.\n")] * 4)
        m["layout_delta"] = -0.25
        assert "layout moves this measurement" in render("raid", m)

    def test_stays_quiet_when_layout_is_irrelevant(self) -> None:
        m = measure([(_HUMAN, _AI)] * 4)
        m["layout_delta"] = 0.0
        assert "layout moves this measurement" not in render("raid", m)


def test_excluding_a_category_isolates_its_contribution() -> None:
    """The property that made the drift diagnosable.

    Dropping the two repetition tells from the live catalogue reproduced 0.6379 on RAID, matching
    the 0.638 written before those categories existed. That is how the figure was shown to be stale
    rather than wrong, so the mechanism it relies on is pinned here.
    """
    from untell.scripts.tells import score_tells

    text = _AI * 6  # long enough for the repetition tells to be eligible
    fired = score_tells(text)["by_category"]
    assert fired, "probe must fire something for the exclusion to mean anything"

    from eval.tells_auroc import _rate

    full = _rate(text)
    without = _rate(text, frozenset(fired))
    assert without == 0.0
    assert full > without


def test_layout_categories_are_the_line_anchored_ones() -> None:
    assert LAYOUT_CATEGORIES == {"markdown_artifact", "title_case_heading", "diff_anchored"}


def test_collapse_layout_preserves_words() -> None:
    text = "One two.\n\nThree   four.\tFive."
    assert collapse_layout(text).split() == text.split()
