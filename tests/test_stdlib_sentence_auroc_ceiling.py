"""Stdlib per-sentence AUROC ceiling — near-chance on both HC3 and RAID.

WHAT
    The pure-stdlib (no-torch) path for per-sentence scoring is near-chance.
    Measured AUROC: 0.513 on HC3, 0.516 on RAID (50 docs each, ~830 and ~1000
    sentences, re-measured 2026-08-21 with UNTELL_LITE_NO_TORCH=1).

ROOT CAUSE
    Three signals are available to the stdlib path at sentence granularity:
      1. Tell density (`score_tells`) — fires only when a sentence contains a
         characteristic AI phrase ("Moreover", "Furthermore", etc.).  On most
         sentences it returns 0, contributing nothing.
      2. Common-word ratio — capped at 0.25 (below the detection threshold)
         because casual human speech is nearly all common words and the term
         is inverted for modern AI prose.  Anything with common-word ratio
         >= 0.45 returns exactly 0.25, which is the majority of all sentences.
      3. Burstiness (CV of sentence lengths) — only defined over multiple
         sentences; undefined for a single sentence scored in isolation.

    Result: 86% of HC3 sentences and 44% of RAID sentences pin to exactly 0.25.
    The ranking is equivalent to choosing the worst-third at random.

ACCEPTANCE (Issue #23)
    The tool already emits `UNINFORMATIVE_TARGETING_WARNING` when the stdlib
    path is the sole scorer, and returns `warning` in the result dict.  These
    tests pin (a) the degenerate score distribution on typical input, and (b)
    the AUROC ceiling against real labelled data on both corpora.
"""

from __future__ import annotations

import os

import pytest

# ---------------------------------------------------------------------------
# Fast (no external data) — degenerate score distribution
# ---------------------------------------------------------------------------

# Sentences that a human would write: no AI-characteristic tells.  The
# common-word ratio is high for both human and AI sentences, so both collapse
# to the same score under the stdlib heuristic.
_PLAIN_HUMAN = [
    "I went to the store yesterday and bought some milk.",
    "The dog barked twice and then ran back inside the house.",
    "She read the last few pages and closed the book.",
    "We tried it twice but it still did not work.",
    "He asked me what time the meeting was supposed to start.",
    "The train arrived ten minutes late because of the weather.",
    "My daughter drew a picture of a cat on the wall.",
    "They fixed the leak in the roof last Tuesday.",
    "I had no idea how long the line would be.",
    "The keys were on the kitchen table all along.",
]

# Sentences in a bland AI style but WITHOUT explicit tell-words.  The stdlib
# path should score these at approximately the same value as the human ones.
_PLAIN_AI_NO_TELLS = [
    "The organization has developed a robust framework for addressing these challenges.",
    "The findings suggest that the implementation strategy requires further refinement.",
    "This approach enables stakeholders to align their objectives with broader goals.",
    "The methodology incorporates several key components that enhance overall effectiveness.",
    "The data indicates a positive correlation between the two variables studied.",
    "The results demonstrate the viability of the proposed solution in this context.",
    "The team evaluated multiple options before settling on the most appropriate course of action.",
    "The analysis reveals that current practices may benefit from systematic improvement.",
    "The initiative aims to streamline processes while maintaining quality standards.",
    "The evidence supports the conclusion that further investigation is warranted.",
]


def _stdlib_score(text: str) -> float | None:
    """Score a single sentence on the stdlib path (UNTELL_LITE_NO_TORCH=1)."""
    orig = os.environ.get("UNTELL_LITE_NO_TORCH")
    os.environ["UNTELL_LITE_NO_TORCH"] = "1"
    try:
        from untell.detectors.perplexity_burstiness import lite_score
        return lite_score(text)
    finally:
        if orig is None:
            os.environ.pop("UNTELL_LITE_NO_TORCH", None)
        else:
            os.environ["UNTELL_LITE_NO_TORCH"] = orig


def test_most_plain_sentences_pin_to_the_same_score() -> None:
    """86% of HC3 and 44% of RAID sentences collapse to one value under stdlib.

    On typical sentences without AI-characteristic tell phrases, the common-word
    ratio is >= 0.45 for both human and AI text, so `min(common_signal, 0.25)`
    returns exactly 0.25 for nearly all of them.  Tell density is 0 (no tells
    fire).  The result: the score distribution degenerates to a constant,
    making the ranking arbitrary.
    """
    all_sentences = _PLAIN_HUMAN + _PLAIN_AI_NO_TELLS
    scores = [_stdlib_score(s) for s in all_sentences]
    # Filter out None (too-short sentences — none expected here)
    scores = [s for s in scores if s is not None]
    assert scores, "no sentences scored — check MIN_WORDS threshold"

    # At least 60% should share the same score value.  The measured rate is
    # 86% on HC3 and 44% on RAID; this threshold stays well below both.
    most_common = max(scores, key=scores.count)
    pinned_frac = scores.count(most_common) / len(scores)
    assert pinned_frac >= 0.50, (
        f"only {pinned_frac:.0%} of sentences share the same score ({most_common:.4f}); "
        "expected >=50% to collapse to one value on the stdlib path — if the scoring "
        "improved meaningfully, update the ceiling measurement in the warning message and "
        "these thresholds"
    )


def test_plain_ai_sentences_do_not_outscore_plain_human_sentences() -> None:
    """Without tells, the stdlib path cannot separate human from AI.

    The AUROC from 10 plain-AI vs 10 plain-human sentences should be near 0.5.
    A result above 0.70 would mean the common-word or tell signal improved
    substantially — update the ceiling numbers if so.
    """
    human_scores = [_stdlib_score(s) for s in _PLAIN_HUMAN if _stdlib_score(s) is not None]
    ai_scores = [_stdlib_score(s) for s in _PLAIN_AI_NO_TELLS if _stdlib_score(s) is not None]
    if not human_scores or not ai_scores:
        pytest.skip("no scores produced — check MIN_WORDS threshold")

    wins = sum(
        (a > h) + 0.5 * (a == h) for a in ai_scores for h in human_scores
    )
    auc = wins / (len(ai_scores) * len(human_scores))
    assert auc < 0.70, (
        f"stdlib path produced AUROC {auc:.3f} on these plain sentences — "
        "above the near-chance ceiling. If the signal improved, update the "
        "warning message in sentences.py with new measurements on HC3 and RAID."
    )


def test_warning_result_key_present_on_stdlib_path(monkeypatch) -> None:
    """score_sentences returns a 'warning' key on the stdlib path.

    The log line fires once per process; the result key fires on every call,
    which is what a machine client (API, MCP) can actually see.
    """
    from untell.detectors.perplexity_burstiness import PerplexityBurstinessDetector
    from untell.scripts.sentences import score_sentences

    monkeypatch.setattr(PerplexityBurstinessDetector, "_torch_ready", lambda self: False)

    result = score_sentences(
        "The cat sat on the mat and looked at the door. The dog barked outside.",
        tier="lite",
    )
    assert "warning" in result, (
        "expected a 'warning' key in the result on the stdlib path; "
        "callers that check this key will silently receive no caveat"
    )
    assert "near-chance" in result["warning"], (
        f"warning text does not mention 'near-chance': {result['warning']!r}"
    )


# ---------------------------------------------------------------------------
# Slow (needs HC3 + RAID via HuggingFace) — real AUROC ceiling measurement
# ---------------------------------------------------------------------------


def _auroc(ai: list[float], human: list[float]) -> float | None:
    if not ai or not human:
        return None
    wins = sum((a > h) + 0.5 * (a == h) for a in ai for h in human)
    return wins / (len(ai) * len(human))


@pytest.mark.slow
def test_stdlib_per_sentence_auroc_below_chance_ceiling_hc3() -> None:
    """AUROC of stdlib-path per-sentence scoring stays near chance on HC3.

    Measured 2026-08-21: AUROC 0.513 on 50 docs (410 human + 422 AI sentences,
    MIN_WORDS=8).  Root cause: 86% of sentences pin to 0.25 (the common-word
    ceiling) with no tells firing.

    This test fails if the stdlib path improves meaningfully — which is what
    we want, but if it happens the warning message and docstrings must be
    updated to reflect the new measurement.
    """
    from eval.datasets import load_pairs
    from untell.detectors.perplexity_burstiness import lite_score
    from untell.text_split import split_sentences

    pairs = load_pairs("hc3", 50)
    if len(pairs) < 30:
        pytest.skip(f"HC3 unavailable (got {len(pairs)} pairs)")

    orig = os.environ.get("UNTELL_LITE_NO_TORCH")
    os.environ["UNTELL_LITE_NO_TORCH"] = "1"
    try:
        min_words = 8
        human_scores, ai_scores = [], []
        for h_doc, ai_doc in pairs:
            for s in split_sentences(h_doc):
                if len(s.split()) >= min_words:
                    v = lite_score(s)
                    if v is not None:
                        human_scores.append(v)
            for s in split_sentences(ai_doc):
                if len(s.split()) >= min_words:
                    v = lite_score(s)
                    if v is not None:
                        ai_scores.append(v)
    finally:
        if orig is None:
            os.environ.pop("UNTELL_LITE_NO_TORCH", None)
        else:
            os.environ["UNTELL_LITE_NO_TORCH"] = orig

    assert len(human_scores) >= 100 and len(ai_scores) >= 100, (
        f"too few sentences: human={len(human_scores)} ai={len(ai_scores)}"
    )
    auc = _auroc(ai_scores, human_scores)
    assert auc is not None
    # Must stay near-chance (< 0.55).  Measured 0.513; failing here means the
    # stdlib signal improved — update the warning message if so.
    assert auc < 0.55, (
        f"HC3 stdlib AUROC {auc:.4f} is above 0.55 — if the signal genuinely "
        "improved, update UNINFORMATIVE_TARGETING_WARNING and docstrings in "
        "untell/scripts/sentences.py with the new measurement"
    )
    # Root-cause check: most sentences must share the same score value.
    all_scores = human_scores + ai_scores
    most_common = max(all_scores, key=all_scores.count)
    pinned = sum(s == most_common for s in all_scores) / len(all_scores)
    assert pinned >= 0.50, (
        f"only {pinned:.0%} of HC3 sentences at the most common score ({most_common:.4f}); "
        "if degenerate pinning improved, update the '86%' figure in the warning message"
    )


@pytest.mark.slow
def test_stdlib_per_sentence_auroc_below_chance_ceiling_raid() -> None:
    """AUROC of stdlib-path per-sentence scoring stays near chance on RAID.

    Measured 2026-08-21: AUROC 0.516 on 50 docs (416 human + 588 AI sentences,
    MIN_WORDS=8).  Root cause: 44% of sentences pin to 0.25 on RAID (lower than
    HC3 because RAID generators vary more, producing more AI-characteristic tells).
    """
    from eval.datasets import load_pairs
    from untell.detectors.perplexity_burstiness import lite_score
    from untell.text_split import split_sentences

    pairs = load_pairs("raid", 50)
    if len(pairs) < 30:
        pytest.skip(f"RAID unavailable (got {len(pairs)} pairs)")

    orig = os.environ.get("UNTELL_LITE_NO_TORCH")
    os.environ["UNTELL_LITE_NO_TORCH"] = "1"
    try:
        min_words = 8
        human_scores, ai_scores = [], []
        for h_doc, ai_doc in pairs:
            for s in split_sentences(h_doc):
                if len(s.split()) >= min_words:
                    v = lite_score(s)
                    if v is not None:
                        human_scores.append(v)
            for s in split_sentences(ai_doc):
                if len(s.split()) >= min_words:
                    v = lite_score(s)
                    if v is not None:
                        ai_scores.append(v)
    finally:
        if orig is None:
            os.environ.pop("UNTELL_LITE_NO_TORCH", None)
        else:
            os.environ["UNTELL_LITE_NO_TORCH"] = orig

    assert len(human_scores) >= 100 and len(ai_scores) >= 100, (
        f"too few sentences: human={len(human_scores)} ai={len(ai_scores)}"
    )
    auc = _auroc(ai_scores, human_scores)
    assert auc is not None
    assert auc < 0.55, (
        f"RAID stdlib AUROC {auc:.4f} is above 0.55 — if the signal genuinely "
        "improved, update UNINFORMATIVE_TARGETING_WARNING and docstrings in "
        "untell/scripts/sentences.py with the new measurement"
    )
