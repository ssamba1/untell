"""The loop's top-level `warning` must carry the SCORE's caveat, not just the scrub payload.

`carried_payload` (hidden characters) was the only thing that ever reached `result["warning"]`, so
a caller reading the documented top-level field got None while `post["warning"]` said

    "no detector produced a score — max/mean are placeholders, not a verdict"

MEASURED on Chinese input: `changed=False`, `rewrites=3`, top-level warning None, and a `flagged`
boolean computed from placeholder maxima. Same shape as the `scored: False` problem `_bypass_rate`
already guards — the information exists on the result and the summary line does not carry it.
"""

from __future__ import annotations

import pytest

from untell.scripts.run import _merge_warnings, untell_text

NOT_ENGLISH = "此外，该框架利用强大的方法在规模上提供成果。而且，它显著提高了整体效率和准确性。"

LONG_ENGLISH = (
    "The committee reviewed the proposal and found it broadly acceptable, though several members "
    "raised concerns about the timeline and the budget, which the chair agreed to revisit at the "
    "next meeting before the quarterly planning session began in earnest that autumn. Costs had "
    "risen steadily since spring, and nobody expected throughput to double within a single quarter."
)


def _run(text: str) -> dict:
    return untell_text(text, tier="lite", threshold=0.0, max_iters=1, rewriter="composite")


class TestMergeWarnings:
    """Two independent caveats can apply at once; an `or` between them drops the second."""

    def test_nothing_to_say_is_none(self):
        assert _merge_warnings(None, None) is None
        assert _merge_warnings("", "   ") is None

    def test_a_single_part_passes_through(self):
        assert _merge_warnings(None, "b") == "b"

    def test_two_parts_are_joined(self):
        assert _merge_warnings("a", "b") == "a Also: b"

    def test_an_exact_repeat_is_not_said_twice(self):
        assert _merge_warnings("a", "a") == "a"

    def test_order_is_preserved(self):
        assert _merge_warnings("first", "second", "third") == "first Also: second Also: third"


def test_the_scoring_caveat_reaches_the_top_level():
    """The bug: `post["warning"]` said the max was a placeholder and `warning` said nothing."""
    result = _run(NOT_ENGLISH)
    warning = result.get("warning") or ""
    assert warning, "the top-level field must carry the caveat"
    assert "placeholders" in warning, warning


def test_the_language_reason_reaches_the_top_level_too():
    warning = _run(NOT_ENGLISH).get("warning") or ""
    assert "not in a script" in warning, warning


def test_a_clean_run_says_nothing():
    """Guards the guard. A caveat on every run is noise, and noise is how a real one is missed."""
    assert _run(LONG_ENGLISH).get("warning") is None


def test_the_caveat_matches_what_the_score_itself_reported():
    """The two must not disagree — the top-level line is a summary, not a second opinion."""
    result = _run(NOT_ENGLISH)
    post = (result["post"].get("warning") or "").strip()
    assert post, "premise: the score must have had something to say"
    assert post in (result.get("warning") or "")


@pytest.mark.parametrize("text", [NOT_ENGLISH, LONG_ENGLISH, "Hello"])
def test_the_run_still_returns_text_whatever_it_warns(text: str):
    assert _run(text)["final"].strip() or not text.strip()
