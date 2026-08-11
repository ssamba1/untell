"""A ceiling figure is meaningless without the corpus it was measured on.

`docs/free-ceiling-measured.md` opens with a warning that says exactly this, and its own table
shows why:

    built-in demo corpus (37 words)   0.859 -> 0.154   0% still flagged
    real HC3 answers    (195 words)   0.999 -> 0.860   100% still flagged

The same loop, the same settings, and the conclusion inverts. `free-ceiling-report.md` — the
summary anyone reads first — quoted "0.86 -> 0.21, flagged 1.00 -> 0.11" as untell's evidenced
ceiling, named no corpus, carried no spread, and never mentioned the real-text figure at all. The
README had already been corrected for this exact mistake in 2c4a6fb; the report had not.

These tests do not check particular numbers, which would go stale as the measurements are redone.
They check that a document quoting a ceiling also says which corpus produced it.
"""

from __future__ import annotations

import pathlib
import re

_REPORT = pathlib.Path("docs/free-ceiling-report.md").read_text(encoding="utf-8")
_MEASURED = pathlib.Path("docs/free-ceiling-measured.md").read_text(encoding="utf-8")

# "0.859 -> 0.154", "0.86 → 0.21" — a before/after pair, which is what a ceiling claim looks like.
_CEILING_PAIR = re.compile(r"0\.\d{2,3}\s*(?:->|→)\s*\*{0,2}0\.\d{2,3}")


def test_the_report_states_both_corpora() -> None:
    """The demo figure alone reads as a general result. It is not one."""
    assert _CEILING_PAIR.search(_REPORT), "no ceiling figure found — did the wording change?"
    lowered = _REPORT.lower()
    assert "demo corpus" in lowered or "hand-written" in lowered, (
        "the report quotes a ceiling without naming the corpus it came from"
    )
    assert "hc3" in lowered, (
        "the report omits the real-text figure, which is the one that inverts the conclusion"
    )


def test_the_measured_doc_keeps_its_corpus_warning() -> None:
    """The report defers to this file; if the warning goes, the deferral is worthless."""
    assert "Read the corpus before reading any number" in _MEASURED


def test_a_quoted_ceiling_carries_a_spread_or_a_repeat_count() -> None:
    """The rewriters are randomised. `eval/ceiling.py --repeats` says "use >=3 before quoting"."""
    assert "±" in _REPORT or "repeats" in _REPORT.lower(), (
        "ceiling figures are quoted with neither a spread nor a repeat count"
    )
