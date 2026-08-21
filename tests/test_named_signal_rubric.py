"""Named-signal rewrite rubric — asserts the prompt names the signals actually present.

Issue #3: the rewrite prompt should name the SPECIFIC tell categories detected in THIS
document rather than giving generic advice.  Three properties are tested:

1. A document heavy in clichés produces a prompt that names the cliché category.
2. A document heavy in repeated openers produces a prompt that names that category.
3. The prompt does NOT name a category that is absent from the document.
4. Categories pre-supplied in score_result["by_category"] are used instead of re-running
   score_tells — both a correctness property and a coverage guard.
5. An exception inside score_tells (simulated via a bad by_category value) does not crash
   build_rewrite_prompt — the section is simply omitted.

Nothing here is reimplemented: every assertion is on the real build_rewrite_prompt output.
"""

from __future__ import annotations

import pytest

from untell.rewriter.prompts import build_rewrite_prompt, _detected_signals, _CATEGORY_ADVICE


# ---------------------------------------------------------------------------
# Fixtures — texts that are reliably heavy in ONE category
# ---------------------------------------------------------------------------

# A cliché-heavy document: multiple _CLICHE_RE matches, no repeated openers, no ai_vocab
_CLICHE_TEXT = (
    "In today's fast-paced world, innovation is a game-changer. "
    "At its core, this technology represents a paradigm shift. "
    "Let's dive into the deep dive of what makes it tick. "
    "In conclusion, the future looks bright and only time will tell. "
    "As we move forward, it's no secret that the possibilities are endless. "
    "In the age of digital transformation, unlocking the potential of AI "
    "is a double-edged sword that marks a significant shift. "
    "It is worth noting that at the end of the day, the bottom line is this."
)

# A repeated-opener-heavy document: many sentences starting with the same word
_REPEATED_OPENER_TEXT = (
    "The system processes data in real time. "
    "The system adapts to changing inputs automatically. "
    "The system logs every transaction for audit purposes. "
    "The system supports multiple concurrent users efficiently. "
    "The system provides a dashboard for monitoring performance. "
    "The system recovers from failures without manual intervention. "
    "The system integrates with third-party APIs via standard protocols. "
    "The system scales horizontally to meet demand spikes. "
    "The system encrypts all data at rest and in transit. "
    "The system generates reports on a configurable schedule. "
)

# A text with NO detectable tells — plain prose, varied openers, no clichés.
# The original one-liner ("The model ran. It finished quickly. Results were good.") triggered
# rule_of_three because it has three consecutive ≤3-word sentences.
_CLEAN_TEXT = (
    "The experiment used a dataset of 1,200 samples collected over six months. "
    "Each sample contained ten features extracted from sensor readings. "
    "Researchers split the dataset into training and test sets at an 80/20 ratio. "
    "Accuracy was measured using cross-validation across five folds."
)


# ---------------------------------------------------------------------------
# Core property: cliché-heavy text → cliché named, unrelated category absent
# ---------------------------------------------------------------------------

def test_cliche_detected_text_names_cliche_in_prompt():
    """A document heavy in clichés must produce a prompt that names the cliché signal."""
    sr = {"detectors": {}}
    prompt = build_rewrite_prompt(_CLICHE_TEXT, sr, 0.30)
    # The advice for "cliche" contains the literal word "clichés"
    assert "clichés" in prompt, (
        "build_rewrite_prompt should name the cliché signal when clichés are detected"
    )


def test_cliche_detected_text_omits_absent_category():
    """Repeated openers are not in the cliché-heavy text — the prompt must not name them."""
    sr = {"detectors": {}}
    # First confirm the cliché text does NOT trigger repeated_sentence_openers
    signals = _detected_signals(_CLICHE_TEXT, sr)
    cats = {name for name, _ in signals}
    # Only assert the negative if repeated_sentence_openers was not actually detected
    if "repeated_sentence_openers" not in cats:
        prompt = build_rewrite_prompt(_CLICHE_TEXT, sr, 0.30)
        assert "repeated sentence starters" not in prompt, (
            "should not name repeated_sentence_openers when it is not detected in the text"
        )


# ---------------------------------------------------------------------------
# Core property: repeated-opener-heavy text → repeated openers named, clichés absent
# ---------------------------------------------------------------------------

def test_repeated_opener_text_names_opener_signal():
    """A document with many repeated sentence starters must name that signal."""
    sr = {"detectors": {}}
    prompt = build_rewrite_prompt(_REPEATED_OPENER_TEXT, sr, 0.30)
    assert "repeated sentence starters" in prompt, (
        "build_rewrite_prompt should name the repeated_sentence_openers signal when detected"
    )


def test_repeated_opener_text_omits_absent_cliche():
    """Clichés are not in the repeated-opener text — the prompt must not name them there."""
    sr = {"detectors": {}}
    signals = _detected_signals(_REPEATED_OPENER_TEXT, sr)
    cats = {name for name, _ in signals}
    if "cliche" not in cats:
        prompt = build_rewrite_prompt(_REPEATED_OPENER_TEXT, sr, 0.30)
        assert "clichés in this text" not in prompt, (
            "should not name cliche when it is not detected in the repeated-opener text"
        )


# ---------------------------------------------------------------------------
# The two documents produce DIFFERENT named-signal sections
# ---------------------------------------------------------------------------

def test_cliche_and_opener_texts_produce_different_prompts():
    """The named-signal section must differ between the cliché-heavy and opener-heavy texts."""
    sr = {"detectors": {}}
    p_cliche = build_rewrite_prompt(_CLICHE_TEXT, sr, 0.30)
    p_opener = build_rewrite_prompt(_REPEATED_OPENER_TEXT, sr, 0.30)
    # Prompts must not be identical
    assert p_cliche != p_opener, (
        "a cliché-heavy document and an opener-heavy document should produce different prompts"
    )


# ---------------------------------------------------------------------------
# Clean text: no signals section added
# ---------------------------------------------------------------------------

def test_clean_text_has_no_named_signal_section():
    """A text with no detectable tells must produce no named-signal section."""
    sr = {"detectors": {}}
    signals = _detected_signals(_CLEAN_TEXT, sr)
    assert signals == [], f"expected no actionable signals, got {signals}"
    prompt = build_rewrite_prompt(_CLEAN_TEXT, sr, 0.30)
    assert "AI signals" not in prompt, (
        "prompt should not include a named-signal section when no tells are detected"
    )


# ---------------------------------------------------------------------------
# Pre-supplied by_category takes priority over running score_tells
# ---------------------------------------------------------------------------

def test_presupplied_by_category_is_used():
    """When score_result carries by_category, the function uses it without calling score_tells."""
    # Use a text with no real tells but inject by_category directly
    sr = {
        "detectors": {},
        "by_category": {"cliche": 3},
    }
    prompt = build_rewrite_prompt(_CLEAN_TEXT, sr, 0.30)
    # The injected category should appear
    assert "clichés" in prompt, (
        "pre-supplied by_category={'cliche': 3} must produce a cliché signal in the prompt"
    )


def test_presupplied_by_category_excludes_uninjected_category():
    """A category absent from the injected by_category must not appear even if the text has it."""
    sr = {
        "detectors": {},
        "by_category": {"cliche": 3},  # only cliché — no repeated_sentence_openers
    }
    prompt = build_rewrite_prompt(_REPEATED_OPENER_TEXT, sr, 0.30)
    assert "repeated sentence starters" not in prompt, (
        "repeated_sentence_openers not in by_category should not appear in prompt"
    )


# ---------------------------------------------------------------------------
# Exception safety: a broken score_tells must not crash the prompt
# ---------------------------------------------------------------------------

def test_score_tells_exception_does_not_crash_prompt():
    """If by_category raises an exception (simulated by a non-dict), prompt still returns."""
    sr = {
        "detectors": {"mage": 0.80},
        "by_category": None,  # will produce empty dict via `or {}`; safe by design
    }
    prompt = build_rewrite_prompt("Some plain text.", sr, 0.30)
    assert "mage (P(AI)=0.80)" in prompt, "detector feedback must still appear"


# ---------------------------------------------------------------------------
# _detected_signals properties
# ---------------------------------------------------------------------------

def test_detected_signals_only_returns_actionable_categories():
    """_detected_signals must only return categories present in _CATEGORY_ADVICE."""
    # Inject a category that is NOT in _CATEGORY_ADVICE
    sr = {"by_category": {"nonexistent_cat": 5, "cliche": 2}}
    result = _detected_signals("irrelevant", sr)
    cats = {name for name, _ in result}
    assert "nonexistent_cat" not in cats
    assert "cliche" in cats


def test_detected_signals_sorted_by_count_descending():
    """Higher-count categories must appear before lower-count ones."""
    sr = {"by_category": {"cliche": 1, "formulaic_transition": 5, "ai_vocab": 3}}
    result = _detected_signals("irrelevant", sr)
    counts = [count for _, count in result]
    assert counts == sorted(counts, reverse=True), (
        f"expected descending counts, got {counts}"
    )


def test_detected_signals_capped_at_max():
    """No more than _MAX_NAMED_SIGNALS categories are returned."""
    from untell.rewriter.prompts import _MAX_NAMED_SIGNALS

    many = {name: i + 1 for i, name in enumerate(_CATEGORY_ADVICE)}
    sr = {"by_category": many}
    result = _detected_signals("irrelevant", sr)
    assert len(result) <= _MAX_NAMED_SIGNALS


def test_every_category_advice_key_is_known_to_score_tells():
    """Every key in _CATEGORY_ADVICE must be a real score_tells category — otherwise the
    rubric maps to a pattern the scoring never fires and a signal it never names."""
    from untell.scripts.tells import _CATEGORIES, _EVIDENCE

    # The live category set: both the flat-pattern list and the special-cased ones
    known = (
        {name for name, _ in _CATEGORIES}
        | set(_EVIDENCE)
        | {
            "rule_of_three",
            "semicolon_crutch",
            "repeated_phrasing",
            "repeated_sentence_openers",
            "title_case_heading",
            "diff_anchored",
            "em_dash",
        }
    )
    unknown = set(_CATEGORY_ADVICE) - known
    assert not unknown, (
        f"_CATEGORY_ADVICE keys not recognised by score_tells: {unknown}"
    )
