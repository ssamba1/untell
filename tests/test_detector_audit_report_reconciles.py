"""The audit's summary line has to be readable beside the table it summarises.

The smoke-test run printed

    fast_detectgpt [sentence]  INVERTED  0.444  ...
    ...
    BROKEN: none — every available detector responds in the correct direction.

Both lines are correct. Sentence rows are deliberately held to AUROC <= 0.20 before counting as
broken, because six probes per class is 36 pairs and a value near chance is noise — measured, the
same detector scores 0.915 on 40 real HC3 sentence pairs, and gating CI on the smoke number would
turn the build red over sampling.

But a reader cannot reconcile those two lines without opening the source, and the summary is the
line people quote. It now names what it excluded and why.

This is the same defect shape as the `verdict`/`flagged` and `mode`/`_torch_ready` pairs elsewhere in
this log: a value that is true about its own computation and misleading next to the data it is
printed beside.
"""

from __future__ import annotations

from eval.detector_audit import SENTENCE_BROKEN_AUROC, render


def _report(rows: list[dict]) -> dict:
    return {"results": rows, "broken": [], "source": "test", "dataset": None, "pairs": 0}


def _row(name: str, verdict: str, auroc: float | None, granularity: str) -> dict:
    return {
        "detector": name, "verdict": verdict, "auroc": auroc, "granularity": granularity,
        "human_mean": 0.3, "ai_mean": 0.2, "gap": -0.1, "fpr": 0.0, "tpr": 0.0,
        "available": True,
    }


def test_an_excused_sentence_verdict_is_named() -> None:
    out = render(_report([_row("fast_detectgpt [sentence]", "INVERTED", 0.444, "sentence")]))
    assert "BROKEN: none" in out
    assert "Not counted: fast_detectgpt [sentence]" in out, out
    assert str(SENTENCE_BROKEN_AUROC) in out, "the bar itself must be stated, not just referenced"


def test_a_genuinely_broken_sentence_row_is_not_excused() -> None:
    """Below the bar is a real inversion — 36 pairs cannot produce 0.000 by chance. It must not
    appear in the excused list, or the caveat becomes a way to hide the defect it was written to
    contextualise."""
    out = render(_report([_row("pb [sentence]", "INVERTED", 0.0, "sentence")]))
    assert "Not counted" not in out, out


def test_a_paragraph_verdict_is_never_excused() -> None:
    """The bar exists for small sentence samples only. A paragraph-level inversion is the thing
    this audit is for."""
    out = render(_report([_row("pb", "INVERTED", 0.444, "paragraph")]))
    assert "Not counted" not in out, out


def test_a_clean_report_says_nothing_extra() -> None:
    """Guards the guard. A note appended to every run is noise, and noise is how a real one is
    missed."""
    out = render(_report([_row("pb", "OK", 0.96, "paragraph"),
                          _row("pb [sentence]", "OK_SEPARATED", 1.0, "sentence")]))
    assert "BROKEN: none" in out
    assert "Not counted" not in out, out


def test_the_summary_and_the_table_cannot_contradict() -> None:
    """The invariant, stated directly: any row whose verdict is bad appears either in the broken
    list or in the excused note. A reader must never see a bad verdict the summary is silent
    about."""
    rows = [
        _row("a", "INVERTED", 0.444, "sentence"),
        _row("b", "OK", 0.9, "paragraph"),
        _row("c", "MISCALIBRATED", 0.8, "sentence"),
    ]
    out = render(_report(rows))
    for row in rows:
        if row["verdict"] in ("DEAD", "INVERTED", "MISCALIBRATED"):
            assert row["detector"] in out, f"{row['detector']} has a bad verdict and is unmentioned"
