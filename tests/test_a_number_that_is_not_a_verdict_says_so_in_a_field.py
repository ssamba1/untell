"""The tool asserted a verdict on a path measured as unable to support one, in prose only.

Round 116 calibrated the stdlib scoring path per length band on 6,810 pre-ChatGPT documents — text
that cannot be AI-generated — and found the false-positive rate fixable only at the cost of the
detection it exists for:

    band       FPR at 0.45  FPR calibrated   TPR at 0.45  TPR calibrated
    50-100           29.1%            3.6%          9.3%           2.3%
    100-200          15.8%            4.8%          9.1%           0.0%

There is no threshold at which that path both catches AI text and leaves human text alone, and round
116 concluded exactly that. But `score_text` went on returning `flagged` and `ai_percent` — fields
that ASSERT an answer — with the caveat carried only in `warning`.

⚠️ **A caveat competing with a percentage loses, and that is now measured rather than assumed.** Du
et al. (Front. Psychol., doi:10.3389/fpsyg.2026.1889402, retrieved from PubMed) gave 214 university
teachers the SAME medium-quality paper with a fictitious detection report attached, varying only the
reported rate — 7% against 87%. The high rate lowered their judgements of originality, language
expression and logical structure, of writing that had not changed a word.

FOUND by auditing a claim made one round earlier. Round 130 said that finding "converts three of
this repo's reporting choices from taste into requirements", listing "refusing to print a verdict a
tier cannot support" among them — and the repo had not made that choice. The claim credited it with
work it had not done.

`verdict_supported` is the fix, deliberately ADDITIVE: `flagged` and `ai_percent` keep their
meanings and every existing consumer keeps working. What is new is a boolean a caller can act on
instead of parsing English.
"""

from __future__ import annotations

from untell.scripts.score import _verdict_supported, score_text

SAMPLE = (
    "The framework leverages robust methodologies to deliver outcomes at scale. Moreover, it "
    "underscores the pivotal role of stakeholder engagement in navigating the complex landscape "
    "of modern organisational transformation across a range of operating contexts."
)


def test_the_field_is_always_present_so_a_caller_can_rely_on_it() -> None:
    """An optional honesty field is one nobody checks. `.get('verdict_supported', True)` would
    default to trusting the number, which is the failure mode this exists to remove."""
    result = score_text(SAMPLE, tier="lite")
    assert "verdict_supported" in result
    assert isinstance(result["verdict_supported"], bool)


def test_a_stdlib_only_ensemble_reports_that_it_cannot_support_a_verdict() -> None:
    assert _verdict_supported({"perplexity_burstiness": "stdlib"}) is False
    assert _verdict_supported({"a": "stdlib", "b": "stdlib"}) is False


def test_one_supported_detector_is_enough() -> None:
    """False is a statement about the whole ensemble that ran, not about its weakest member. A rule
    that went False whenever ANY detector was weak would fire on every mixed run and be ignored."""
    assert _verdict_supported({"a": "stdlib", "b": "model"}) is True
    assert _verdict_supported({"a": "model"}) is True


def test_nothing_live_is_not_a_supported_verdict() -> None:
    """The empty case has to go False, not True. An ensemble with no live detector produces the
    unscored placeholder — max 0.0 — and 0.0 below a threshold reads as a clean bill of health, which
    is the trap this repo has found at eight separate sites."""
    assert _verdict_supported({}) is False


def test_the_existing_fields_are_untouched() -> None:
    """Additive means additive. A consumer reading `flagged` or `ai_percent` must see exactly what it
    saw before, or this is a breaking change wearing an honesty label."""
    result = score_text(SAMPLE, tier="lite")
    assert "flagged" in result and isinstance(result["flagged"], bool)
    assert "ai_percent" in result and isinstance(result["ai_percent"], (int, float))
    # And the new field must not be silently agreeing with `flagged` — they answer different
    # questions, and a reader who conflates them learns nothing.
    assert result["verdict_supported"] is False, (
        "this environment has no torch, so the stdlib path should report an unsupported verdict"
    )


def test_the_field_is_documented_where_callers_look() -> None:
    """`docs/result-shapes.md` carries the canonical key list, and a key absent from it is a key
    nobody discovers — the same defect round 129 found in two whole modules."""
    from pathlib import Path

    doc = Path("docs/result-shapes.md").read_text(encoding="utf-8")
    assert "verdict_supported" in doc
    # In the key LIST, not only in prose further down.
    header = doc[doc.index("## Full key lists"):]
    assert "verdict_supported" in header[:600], "the key list itself must name it"
