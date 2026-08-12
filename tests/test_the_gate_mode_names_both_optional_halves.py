"""`meaning_gate` said "nli" while the larger half of the guarantee was silently absent.

The field exists to tell a caller which fidelity checks were actually in force, and `"nli"` is
documented as "the full conjunction ... plus the predicate-argument role check". It was computed
from the NLI import alone. With spaCy's model missing, `role_swap` returns None — correctly, since
an unavailable check must never become a veto — and the mode still reported `"nli"`.

That is the larger half. MEASURED over 49 genuine rewrites from three rewriters across 20 HC3 and
RAID documents, every gate evaluated separately:

    numerals 0    certainty 0    polarity 0    similarity 0
    contradiction 1    role_swap 2    entailment 0

Two of the three vetoes the whole conjunction produced came from the check the mode string did not
mention. `"nli (no role check)"` is its own value rather than being folded into either neighbour: it
is strictly stronger than `"similarity-only"` — contradiction and entailment still run — and
strictly weaker than `"nli"`, and a caller comparing runs across installs needs to see which.

`parser_available()` is separate from calling `role_swap` and reading None, because None is also
what an empty pair returns. "This pair had no roles to compare" and "this install cannot compare
roles" are different facts and only the second is a missing guarantee.
"""

from __future__ import annotations

import logging

import pytest

import untell.scripts.roles as roles
from untell.scripts.roles import parser_available, role_swap
from untell.scripts.run import _meaning_gate_mode


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


def test_the_mode_reports_a_missing_parser(monkeypatch) -> None:
    monkeypatch.setattr(roles, "_load", lambda: None)
    assert _meaning_gate_mode(True) == "nli (no role check)"


def test_the_mode_says_plain_nli_when_both_are_present() -> None:
    """Guards the guard. If this drifted to always reporting the caveat, the value would stop
    carrying information and every run would look degraded."""
    if not parser_available():
        pytest.skip("spaCy model not installed in this environment")
    from untell.scripts.entailment import available

    if not available():
        pytest.skip("NLI not installed in this environment")
    assert _meaning_gate_mode(True) == "nli"


def test_a_disabled_veto_still_wins(monkeypatch) -> None:
    """Order matters: switching the veto off removes contradiction AND entailment, which is a
    bigger loss than the role check, so it must not be masked by the new value."""
    monkeypatch.setattr(roles, "_load", lambda: None)
    assert _meaning_gate_mode(False) == "similarity-only (veto disabled)"


def test_availability_is_not_inferred_from_a_none_verdict() -> None:
    """`role_swap` returns None for an unavailable parser AND for empty input. Reading None as
    "unavailable" would report a missing guarantee on a pair that simply had nothing to compare."""
    if not parser_available():
        pytest.skip("spaCy model not installed in this environment")
    assert role_swap("", "") is None
    assert parser_available() is True


def test_the_three_values_are_ordered_by_what_is_running(monkeypatch) -> None:
    """The vocabulary is a ladder, and its rungs must stay distinct — two of them collapsing into
    one is exactly the bug this file exists for."""
    monkeypatch.setattr(roles, "_load", lambda: None)
    degraded = _meaning_gate_mode(True)
    disabled = _meaning_gate_mode(False)
    assert degraded != disabled
    assert degraded.startswith("nli") and disabled.startswith("similarity-only")
