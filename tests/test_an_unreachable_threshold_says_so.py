"""A threshold of 45 passed everything on every surface, including the one that exits 0 in CI.

FOUND by sweeping the library path for values the CLI and REST would reject — the generalisation of
Result 180, where the library entry point was the one surface with no guard on a name. Detector
scores are probabilities: every checker in the registry clamps to [0, 1]. A threshold outside that
range is therefore not a strict setting, it is an unreachable one.

MEASURED on the same AI paragraph, across all three surfaces:

    threshold   score.flagged   untell.flagged   verify.passes_all
        0.30          True             True            False
        0.45          True             True            False
        1.50          False            False           True
       45.00          False            False           True
       -1.00          True             True            False

A caller who types `45` meaning 45 per cent gets a clean verdict everywhere, and `verify` — the
CI-facing command — exits 0. **Nothing said a word.** The only warning present was the generic lite
caveat, byte-identical at 0.30 and at 45.00, and it quotes "the 0.30 loop threshold", a number the
caller did not use. The first probe of this scored it as "a warning mentioning the threshold exists"
and had to be re-read: a keyword match on generic prose is not evidence.

`verify` needed its own wiring. It already had a `caveats` list and emitted `warning` conditionally —
undocumented in `result-shapes.md`, the same class as Result 174 — and the note now joins it there,
which is where it matters most.

A warning rather than a refusal, matching how this tool treats an unknown tier and an unknown style:
the run still happens and the caller is told what their setting actually did.

The valid boundaries stay silent. 0.0 and 1.0 are reachable — a score can equal either — so warning
about them would be noise on a legitimate, if extreme, setting.
"""

from __future__ import annotations

import logging

import pytest

from untell.scripts.run import untell_text
from untell.scripts.score import _threshold_range_warning, score_text
from untell.scripts.verify import verify

TEXT = (
    "Moreover, the framework leverages a robust approach to delivery at scale. "
    "Furthermore, it is important to note that this underscores the pivotal integration."
)
MARK = "probabilities in [0, 1]"


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


@pytest.mark.parametrize("threshold", [1.5, 45.0, 100.0])
def test_a_threshold_above_one_says_it_passes_everything(threshold: float) -> None:
    note = _threshold_range_warning(threshold)
    assert note and "above 1.0" in note and "passes everything" in note


@pytest.mark.parametrize("threshold", [-0.01, -1.0])
def test_a_threshold_below_zero_says_it_flags_everything(threshold: float) -> None:
    note = _threshold_range_warning(threshold)
    assert note and "below 0.0" in note and "flags everything" in note


@pytest.mark.parametrize("threshold", [0.0, 0.3, 0.45, 1.0])
def test_a_reachable_threshold_says_nothing(threshold: float) -> None:
    """Guards the guard, including both endpoints. A score can equal 0.0 or 1.0, so those are
    extreme settings rather than impossible ones and must not be warned about."""
    assert _threshold_range_warning(threshold) is None


def test_the_note_names_the_percentage_mistake() -> None:
    """The likeliest way to arrive here is typing a percentage. A caveat that does not name the
    cause leaves the reader to guess which of their numbers is wrong."""
    assert "divide by 100" in (_threshold_range_warning(45.0) or "")


@pytest.mark.parametrize("value", [None, "0.45", True])
def test_a_non_numeric_threshold_is_not_this_check_s_business(value) -> None:
    """`True` is an int in Python and would otherwise read as 1.0. A type error belongs to whoever
    validates types, and inventing a range complaint about it would be a wrong diagnosis."""
    assert _threshold_range_warning(value) is None


def test_it_reaches_score_text() -> None:
    assert MARK in (score_text(TEXT, tier="lite", threshold=45.0).get("warning") or "")
    assert MARK not in (score_text(TEXT, tier="lite", threshold=0.3).get("warning") or "")


def test_it_reaches_untell_text() -> None:
    result = untell_text(
        TEXT, tier="lite", threshold=45.0, max_iters=1, rewriter="structural", best_of=1, seed=1
    )
    assert MARK in (result.get("warning") or "")


def test_it_reaches_verify_which_is_the_one_that_exits_zero() -> None:
    """The case that matters most: a bar no score can reach turns a CI gate green in silence."""
    result = verify(TEXT, tier="lite", threshold=45.0)
    assert result.get("passes_all") is True, "the premise: this is the silent pass being warned about"
    assert MARK in (result.get("warning") or "")
    assert MARK not in (verify(TEXT, tier="lite", threshold=0.3).get("warning") or "")


def test_verifys_existing_caveats_still_come_through() -> None:
    """The note joins a list rather than replacing it. `verify` already reported hidden characters
    and homoglyphs, and an out-of-range threshold must not silence them."""
    hidden = TEXT.replace(" the framework", "​ the framework")
    warning = verify(hidden, tier="lite", threshold=45.0).get("warning") or ""
    assert MARK in warning
    assert len(warning) > len(_threshold_range_warning(45.0) or ""), warning
