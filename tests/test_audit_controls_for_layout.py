"""A paired AUROC must measure the prose, not how the corpus was stored.

RAID's human documents are hard-wrapped scrapes and its machine continuations are not: 84.52 single
newlines per 1,000 words against 2.79, and double newlines 0.00 against 14.50. MEASURED, that is
enough on its own — newline density with every word discarded separates RAID's two halves at AUROC
1.0000. A detector that reads nothing and counts line breaks is perfect on this corpus.

The audit therefore collapses layout on both halves before scoring, and reports the layout-only
figure so a corpus with this defect announces itself rather than being trusted. What the detectors
were actually taking from it was smaller than the ceiling allowed (60 pairs, as-supplied ->
collapsed): roberta_openai 0.9406 -> 0.8875, hc3_roberta 0.9975 -> 0.9881, mage unchanged. Inflated
by up to 0.053, not fabricated.

The collapse runs on every corpus, not just RAID: layout-only AUROC is 1.0000 on RAID, 0.9667 on
HC3 and 0.5000 on MAGE. MAGE is the control that shows the fix is free — on a corpus whose layout
carries no class information, collapsing it moves all five detectors by exactly 0.0000.
"""

from __future__ import annotations

import pytest

from eval.detector_audit import LAYOUT_SHORTCUT_WARN, _layout_only_auroc, collapse_layout, render


class TestCollapseLayout:
    def test_every_whitespace_run_becomes_one_space(self) -> None:
        assert collapse_layout("a\n\nb   c\td") == "a b c d"

    def test_wrapped_and_unwrapped_text_become_identical(self) -> None:
        """The whole point: two storage conventions for the same words stop being distinguishable."""
        wrapped = "The committee met\non Tuesday and\npublished its findings."
        flowed = "The committee met on Tuesday and published its findings."
        assert collapse_layout(wrapped) == collapse_layout(flowed)

    def test_words_are_preserved(self) -> None:
        text = "One two three.\n\nFour five six."
        assert collapse_layout(text).split() == text.split()

    def test_leading_and_trailing_whitespace_goes(self) -> None:
        assert collapse_layout("\n  padded  \n") == "padded"


class TestLayoutOnlyAuroc:
    def test_detects_a_corpus_split_by_line_wrapping(self) -> None:
        """RAID's shape: one half hard-wrapped, the other flowing. No words differ."""
        human = ["one\ntwo\nthree four five"] * 5
        ai = ["one two three four five"] * 5
        assert _layout_only_auroc(human, ai) == 1.0

    def test_reports_the_shortcut_whichever_way_it_points(self) -> None:
        """A corpus whose MACHINE half has the newlines is equally compromised."""
        human = ["one two three four five"] * 5
        ai = ["one\ntwo\nthree four five"] * 5
        assert _layout_only_auroc(human, ai) == 1.0

    def test_matched_layout_scores_chance(self) -> None:
        assert _layout_only_auroc(["a b c"] * 5, ["d e f"] * 5) == 0.5

    def test_chance_is_below_the_warning_bar_and_a_split_corpus_is_above(self) -> None:
        assert _layout_only_auroc(["a b c"] * 5, ["d e f"] * 5) < LAYOUT_SHORTCUT_WARN
        assert _layout_only_auroc(["a\nb"] * 5, ["a b"] * 5) >= LAYOUT_SHORTCUT_WARN

    @pytest.mark.parametrize("human,ai", [([], []), (["a"], []), ([], ["a"])])
    def test_empty_input_returns_none_rather_than_a_number(self, human, ai) -> None:
        assert _layout_only_auroc(human, ai) is None


class TestReportSurfacesTheShortcut:
    def _report(self, shortcut):
        return {
            "source": "raid labelled pairs (n=60, layout collapsed)",
            "layout_shortcut": shortcut,
            "results": [],
            "broken": [],
        }

    def test_a_compromised_corpus_is_called_out(self) -> None:
        out = render(self._report(1.0))
        assert "layout-only AUROC" in out
        assert "layout alone nearly separates this corpus" in out

    def test_a_clean_corpus_reports_the_number_without_the_warning(self) -> None:
        out = render(self._report(0.51))
        assert "layout-only AUROC" in out
        assert "nearly separates" not in out

    def test_packaged_probes_report_no_layout_line(self) -> None:
        """Hand-written probes are not a corpus; there is nothing to diagnose."""
        out = render({"source": "packaged probes (smoke test)", "results": [], "broken": []})
        assert "layout-only AUROC" not in out
