"""Composite must not call score_text for draws where polished == text.

Issue #25: composite burned ~12 no-op draws per doc, each calling score_text().
A no-op draw (polished == input text) cannot beat the incumbent since it has the
same score; calling score_text() on it is purely wasteful.

BEFORE the fix: score_text is called for every draw including no-ops.
AFTER the fix:  score_text is skipped when polished == text.

The baseline score_text call (to establish the initial best_score) is expected;
only draw-level scoring calls for no-op candidates are skipped.
"""

from __future__ import annotations

import pytest

# Plain text with no AI tells: no formulaic transitions, no AI vocabulary,
# single sentence so no merging/splitting/opener-variation can fire.
# Both structural and surgical return this text unchanged.
_NOOP_TEXT = "Dogs eat bones."

# A score_text stub that records every call.
_CALLS: list[str] = []


def _stub_score(text: str, *, tier: str = "lite", **_kw) -> dict:
    _CALLS.append(text)
    return {"max": 0.10, "tier": tier, "scores": {"perplexity_burstiness": 0.10}}


@pytest.fixture(autouse=True)
def stdlib_lite(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
    monkeypatch.setenv("UNTELL_DISABLE_MAGE", "1")


@pytest.fixture(autouse=True)
def clear_calls() -> None:  # type: ignore[return]
    _CALLS.clear()
    yield
    _CALLS.clear()


def test_noop_draws_do_not_call_score_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """When all inner draws are no-ops (polished == text), score_text is called at most
    once (the baseline), never once per draw.

    BEFORE fix: score_text called 1 + best_of times (baseline + one per draw).
    AFTER fix:  score_text called 1 time (baseline only; no-op draws skip it).

    SurgicalRewriter.rewrite is mocked to return the input unchanged, eliminating the
    score_text call inside surgical_substitute._score_max from the call count.  That
    call is a surgical-internal detail, not the per-draw outer call this test measures.
    With surgical mocked the only composite-level calls are:
        - 1 baseline at composite.py line 248
        - best_of draw-score calls at composite.py line 279 (BEFORE fix)
        - 0 draw-score calls at composite.py line 279 (AFTER fix)
    """
    monkeypatch.setattr("untell.scripts.score.score_text", _stub_score)

    from untell.rewriter.composite import CompositeRewriter
    from untell.rewriter.surgical import SurgicalRewriter

    # Mock surgical to always return input unchanged (noop), without calling score_text
    # internally.  This isolates the count to composite's own scoring calls only.
    monkeypatch.setattr(
        SurgicalRewriter,
        "rewrite",
        lambda self_rw, text, score_result, threshold=0.30: text,
    )

    best_of = 3
    rw = CompositeRewriter(best_of=best_of)
    score_result = {"tier": "lite", "max": 0.10}
    result = rw.rewrite(_NOOP_TEXT, score_result, threshold=0.30)

    # The result must be the same text (no changes possible on this clean input).
    assert result == _NOOP_TEXT, f"expected unchanged text, got {result!r}"

    # BEFORE fix: 1 (baseline) + best_of draw scores = 4 calls.
    # AFTER fix:  1 (baseline only; noop draws skip score_text) = 1 call.
    assert len(_CALLS) == 1, (
        f"Expected 1 score_text call (baseline only), got {len(_CALLS)}. "
        f"All {best_of} draws produced polished == text (noop) and must not call "
        f"score_text, but {len(_CALLS) - 1} draw-score call(s) were observed."
    )


def test_changing_draw_still_scores(monkeypatch: pytest.MonkeyPatch) -> None:
    """When a draw changes the text, score_text IS called for that candidate.

    Regression guard: the optimisation must not suppress scoring for non-no-op draws.
    """
    monkeypatch.setattr("untell.scripts.score.score_text", _stub_score)

    # A text with formulaic AI tells that structural WILL change.
    ai_text = (
        "Furthermore, the system leverages robust methodologies to deliver outcomes. "
        "In conclusion, these findings underscore the pivotal importance of this approach."
    )

    import random

    from untell.rewriter.composite import CompositeRewriter

    rw = CompositeRewriter(best_of=3)
    score_result = {"tier": "lite", "max": 0.85}
    random.seed(42)
    result = rw.rewrite(ai_text, score_result, threshold=0.30)

    # If at least one draw changed the text, at least one draw-level score_text call
    # must have happened (in addition to the baseline).
    if result != ai_text:
        draw_calls = sum(1 for t in _CALLS if t != ai_text)
        assert draw_calls >= 1, (
            "A draw changed the text but score_text was not called for it. "
            "The no-op skip is incorrectly suppressing scoring for changed draws."
        )
