"""The excused list must never crash, and must never excuse a paragraph verdict.

eval/detector_audit.py:495 — the `excused` comprehension. Commit 3b32835 flipped the
final `and` to `or`, which (a) crashed render() with KeyError('auroc') on any report
containing a row without an 'auroc' key (UNAVAILABLE / AVAIL_ERR / SCORE_ERR /
RETURNED_NONE verdicts — exactly what a smoke run on a machine with opt-in detectors
missing produces), and (b) excused EVERY row with auroc > 0.20, including healthy
paragraph rows and DEAD paragraph detectors, printing a "Not counted:" footnote that
contradicts the BROKEN line above it. The intended logic excuses ONLY sentence rows
with a bad verdict whose AUROC is above the small-sample bar.

This file pins both halves of the fix: no crash on rows without auroc, and no
paragraph/healthy row in the footnote.
"""

from __future__ import annotations

from eval.detector_audit import SENTENCE_BROKEN_AUROC, render


def _scored(name: str, verdict: str, auroc: float, granularity: str | None = None) -> dict:
    row = {
        "detector": name, "verdict": verdict, "human_mean": 0.1, "ai_mean": 0.9,
        "gap": 0.8, "range": 0.8, "auroc": auroc, "fpr": 0.0, "tpr": 0.9, "n": 5,
    }
    if granularity:
        row["granularity"] = granularity
    return row


def _report(rows: list[dict], broken: list[str] | None = None) -> dict:
    return {"results": rows, "broken": broken or [], "source": "test",
            "layout_shortcut": None}


def test_an_unavailable_row_does_not_crash_render() -> None:
    """UNAVAILABLE rows carry no 'auroc' key; the excused scan must skip them, not KeyError."""
    out = render(_report([_scored("roberta_openai", "OK", 0.99), {"detector": "radar", "verdict": "UNAVAILABLE"}]))
    assert "UNAVAILABLE" in out
    assert "Not counted" not in out, out


def test_a_score_error_row_does_not_crash_render() -> None:
    out = render(_report([_scored("roberta_openai", "OK", 0.99),
                          {"detector": "local_judge", "verdict": "SCORE_ERR:RuntimeError"}]))
    assert "SCORE_ERR" in out
    assert "Not counted" not in out, out


def test_healthy_paragraph_rows_are_not_in_the_excused_footnote() -> None:
    """The footnote exists for sentence-granularity small samples; a healthy paragraph
    detector with a high AUROC must not be listed under it."""
    out = render(_report([_scored("roberta_openai", "OK", 0.9925),
                          _scored("hc3_roberta", "OK_SEPARATED", 1.0)]))
    assert "BROKEN: none" in out
    assert "Not counted" not in out, out


def test_a_dead_paragraph_row_is_not_excused() -> None:
    """DEAD at paragraph granularity is the thing this audit exists to report. It must
    appear in the BROKEN line and nowhere else — listing it under 'Not counted' too is
    the self-contradiction the footnote was written to prevent."""
    out = render(_report([_scored("d", "DEAD", 0.90), _scored("ok", "OK", 0.99)], broken=["d"]))
    assert "BROKEN (dead or inverted): d" in out
    assert "Not counted" not in out, out


def test_an_excused_sentence_row_is_still_named() -> None:
    """The intended behaviour survives: a sentence row with a bad verdict and an AUROC
    above the small-sample bar is excused AND named in the footnote."""
    out = render(_report([_scored("fdg [sentence]", "INVERTED", 0.444, "sentence")]))
    assert "Not counted: fdg [sentence]" in out, out


def test_a_miscalibrated_broken_row_is_labelled_honestly() -> None:
    """MISCALIBRATED is a real member of the broken list (mage ships that way on HC3).
    The BROKEN line must say so, not call it "dead or inverted" — the label must not
    contradict the verdict column of the row it names."""
    out = render(_report([_scored("mage", "MISCALIBRATED", 1.0),
                          _scored("ok", "OK", 0.99)], broken=["mage"]))
    assert "BROKEN (dead, inverted, or miscalibrated): mage" in out, out
    assert "BROKEN (dead or inverted): mage" not in out, out


def test_a_dead_broken_row_keeps_the_original_label() -> None:
    """The widened label is conditional: a broken list containing only DEAD/INVERTED
    rows keeps the original wording."""
    out = render(_report([_scored("d", "DEAD", 0.5), _scored("i", "INVERTED", 0.3)],
                         broken=["d", "i"]))
    assert "BROKEN (dead or inverted): d, i" in out, out


def test_derived_sentence_probes_report_the_real_probe_count() -> None:
    """With --pairs the sentence probes are DERIVED from the labelled corpus (up to
    _MAX_SENTENCE_PROBES per class), so the footnote must say how many there actually
    were. Hard-coding "six probes per class is 36 pairs" beside a table whose sentence
    rows show n=30 is the summary-contradicts-table defect this module exists to
    prevent — the reader cannot reconcile the two without opening the source."""
    out = render(_report([_scored("roberta_openai [sentence]", "MISCALIBRATED", 0.8356, "sentence"),
                          _scored("mage [sentence]", "MISCALIBRATED", 0.9283, "sentence")]))
    assert "Not counted: roberta_openai [sentence], mage [sentence]" in out, out
    # the helper sets n=5, which is not > len(SENTENCE_HUMAN_PROBES)=6 -> packaged wording;
    # a real derived run reports its actual count. Pin the packaged wording too:
    assert "six probes per class is 36 pairs" in out, out


def test_a_real_derived_run_names_thirty_probes_per_class() -> None:
    """The derived-probe branch: sentence rows carry the actual per-class count (30 on
    the queue's HC3 run), and the footnote must name it instead of the 36-pair figure."""
    rows = [
        dict(_scored("roberta_openai [sentence]", "MISCALIBRATED", 0.8356, "sentence"), n=30),
        dict(_scored("mage [sentence]", "MISCALIBRATED", 0.9283, "sentence"), n=30),
    ]
    out = render(_report(rows))
    assert "Not counted: roberta_openai [sentence], mage [sentence]" in out, out
    assert "DERIVED from the labelled corpus (30 per class, 900 pairs)" in out, out
    assert "six probes per class is 36 pairs" not in out, out
    assert str(SENTENCE_BROKEN_AUROC) in out, "the bar itself must still be stated"
