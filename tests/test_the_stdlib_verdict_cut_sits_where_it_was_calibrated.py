"""The stdlib verdict cut is a decision about accusing people, and only a range guard held it.

`untell-audit` checks `_STDLIB_PERPLEXITY_VERDICT_THRESHOLD > DEFAULT_THRESHOLD`. That is true of
0.40, 0.35 and 0.31, so any of them could replace the calibrated 0.45 and every check in the repo
would stay green — while the false-positive rate the value was chosen for moved underneath it.

MEASURED, n=100 paired texts per corpus, stdlib path forced (UNTELL_LITE_NO_TORCH=1):

    corpus    FP > 0.30   FP > 0.45   TP > 0.45
    HC3          64%         30%         83%
    RAID         59%         10%         54%
    MAGE         46%          6%         46%

The cut is not re-measured here — that needs three corpus downloads and 600 scores. What is
asserted is that the value shipping today is the one those numbers describe, so a change to it
has to come with a change to the record.
"""
from __future__ import annotations

from untell.scripts.score import (
    DEFAULT_THRESHOLD,
    _STDLIB_PERPLEXITY_VERDICT_THRESHOLD,
    _verdict_threshold,
)

CALIBRATED = 0.45
STDLIB = {"perplexity_burstiness": "stdlib"}
GPT2 = {"perplexity_burstiness": "gpt2"}
STDLIB_ONLY = {"perplexity_burstiness": 0.5}


def test_the_cut_is_the_calibrated_value_not_merely_above_the_loop_target():
    assert _STDLIB_PERPLEXITY_VERDICT_THRESHOLD == CALIBRATED, (
        "the audit only checks this is above the loop target, which 0.40 and 0.31 also satisfy; "
        "if this value moved deliberately, update the per-corpus table in score.py with it"
    )


def test_the_cut_leaves_a_band_wide_enough_to_matter():
    """0.30 -> 0.45 is where FP falls from 64% to 30% on HC3. A narrower band buys little."""
    assert _STDLIB_PERPLEXITY_VERDICT_THRESHOLD - DEFAULT_THRESHOLD >= 0.15


def test_the_raised_cut_applies_only_when_the_heuristic_is_the_whole_verdict():
    """Scoped, or it would soften a verdict that a model-backed detector had earned."""
    assert _verdict_threshold(DEFAULT_THRESHOLD, STDLIB_ONLY, STDLIB) == CALIBRATED
    assert _verdict_threshold(DEFAULT_THRESHOLD, STDLIB_ONLY, GPT2) == DEFAULT_THRESHOLD
    assert _verdict_threshold(
        DEFAULT_THRESHOLD, {**STDLIB_ONLY, "hc3_roberta": 0.9}, STDLIB
    ) == DEFAULT_THRESHOLD


def test_a_caller_asking_for_a_stricter_cut_is_not_loosened():
    """`max`, not assignment. Someone who passed 0.6 wants 0.6, not the heuristic's 0.45."""
    assert _verdict_threshold(0.60, STDLIB_ONLY, STDLIB) == 0.60
