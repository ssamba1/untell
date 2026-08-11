"""Stripping a transition may capitalise what it exposes. Doing nothing may not.

A sentence that OPENS with a locked span has its sentinel set aside as a prefix, leaving `body`
as the mid-sentence remainder. The capitalisation ran even when no transition matched, so that
remainder got upcased and `restore` produced a capital in the middle of a phrase.
"""

from __future__ import annotations

import re

from untell.rewriter.structural import StructuralRewriter

SCORE: dict = {"tier": "full", "max": 1.0, "detectors": {}}

# A capital on a lowercase word that is not sentence-initial, e.g. "New York Times Best seller".
_MID_PHRASE_CAP = re.compile(r"[a-z]{2,}\s+(?:[A-Z][a-z]+\s+){0,3}(Best|Seller|Weekly|List)\b")


def _rewrite(text: str, intensity: float = 1.0) -> str:
    return StructuralRewriter(intensity=intensity).rewrite(text, SCORE, 0.30, intensity=intensity)


def test_a_leading_locked_span_does_not_upcase_the_word_after_it():
    """The measured case, with the entity already masked as `lock()` would leave it."""
    masked = "⟦HZ0001⟧ best seller list is a weekly list that ranks the top books each week."
    for _ in range(12):
        out = _rewrite(masked)
        assert "⟦HZ0001⟧ Best" not in out, out
        assert "Best seller" not in out, out


def test_the_sentinel_itself_survives_untouched():
    masked = "⟦HZ0001⟧ best seller list is a weekly list that ranks the top books each week."
    for _ in range(12):
        assert "⟦HZ0001⟧" in _rewrite(masked)


def test_a_real_transition_after_a_locked_span_is_still_stripped_and_capitalised():
    """The behaviour this guard must not break: a genuine strip still fixes the case."""
    masked = "⟦HZ0002⟧ Moreover, the committee approved the revised budget without debate."
    outs = {_rewrite(masked) for _ in range(40)}
    stripped = [o for o in outs if "Moreover" not in o]
    assert stripped, "premise: the transition must be removable at intensity 1.0"
    for o in stripped:
        assert "⟦HZ0002⟧ the committee" not in o, f"strip left a lowercase clause: {o}"
        assert "⟦HZ0002⟧ The committee" in o, o


def test_an_ordinary_sentence_keeps_its_own_capitalisation():
    plain = "The New York Times best seller list is a weekly list that ranks the top books."
    for _ in range(12):
        out = _rewrite(plain)
        assert "Best seller" not in out, out
        assert not _MID_PHRASE_CAP.search(out), out
