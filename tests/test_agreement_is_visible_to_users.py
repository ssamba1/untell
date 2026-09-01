"""A verdict a user can see must not hide that it is the most accusatory of three readings.

`score_text` computes union / majority / unanimous, but the CLI table showed only the union verdict.
Measured on 72 human abstracts across three detectors, union flags 32 and unanimity flags 0 — so
showing the union alone tells a reader the worst of three answers and calls it the answer.

These tests pin the row's presence and, more importantly, that a single-detector run is labelled as
such rather than rendered as consensus.
"""

from __future__ import annotations

import re
from pathlib import Path

SOURCE = (Path(__file__).resolve().parent.parent / "untell" / "rich_output.py").read_text("utf-8")


def test_the_agreement_row_exists():
    assert 'table.add_row("Agreement"' in SOURCE, "the spread is computed but never displayed"


def test_a_single_detector_run_is_not_rendered_as_unanimous():
    """With one detector the three rules coincide. Printing 'unanimous' would claim an agreement
    that one detector cannot supply — the flattering failure this row exists to avoid."""
    block = SOURCE[SOURCE.index('table.add_row("Agreement"') - 900:]
    assert "degenerate" in block
    assert "1 detector only" in block


def test_the_row_is_justified_by_a_measurement_not_an_opinion():
    """House rule: a display decision that changes what a user concludes carries its number."""
    block = SOURCE[max(0, SOURCE.index('table.add_row("Agreement"') - 1200):]
    assert re.search(r"32 of 72", block), "the row's justification must cite its measurement"
    assert "peerj-cs.2953" in block, "and name the source"
