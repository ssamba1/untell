"""A headline built on `max` cannot show that three of four detectors improved.

MEASURED on HC3, composite, best-of 3, 3 repeats:

    hc3_roberta              0.9992 -> 0.9992      moved by nothing
    roberta_openai           0.9986 -> 0.6228      moved by 0.376
    fast_detectgpt           0.6563 -> 0.4782
    perplexity_burstiness    0.6059 -> 0.5679

    headline: post flagged rate 1.0, mean max P(AI) 0.9997 -> 0.9994

Three detectors improved substantially and the report said the loop achieved nothing, because the
headline is a max and the highest member never budged.

`hc3_roberta` is fine-tuned ON HC3, so against HC3 it is in-distribution: human mean 0.0796, AI mean
0.9992, and the entire spread across 15 AI documents is **1.2e-05**. It discriminates perfectly and
has no dynamic range left to give. On RAID, which it never trained on, the same detector runs 0.0018
human against 0.6953 AI and moves freely.

**Not literally constant, and that distinction is why this file says "pinned" and not "saturated".**
Read at four decimals the AI scores look like exactly 0.9992 every time, and the first reading here
said "constant". Full precision shows 14 distinct values in 15. The practical consequence is the
same — the loop threshold is 0.30 and the spread is a hundred-thousandth — but only one of those two
claims is true.
"""

from __future__ import annotations

import logging

import pytest

from eval.ceiling import _PINNED_DELTA, _pinned_note

PINNED = {
    "per_detector_pre": {"hc3_roberta": 0.9992, "roberta_openai": 0.9986, "fast_detectgpt": 0.6563},
    "per_detector_post": {"hc3_roberta": 0.9992, "roberta_openai": 0.6228, "fast_detectgpt": 0.4782},
}


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


def test_the_pinning_detector_is_named() -> None:
    note = "\n".join(_pinned_note(PINNED))
    assert "hc3_roberta" in note
    assert "0.9992 -> 0.9992" in note


def test_the_best_mover_is_named_with_its_delta() -> None:
    """Naming only the stuck detector would still leave the reader to work out whether anything
    improved. The number that contradicts the headline is the point."""
    note = "\n".join(_pinned_note(PINNED))
    assert "roberta_openai" in note and "0.376" in note


def test_a_run_where_everything_moved_says_nothing() -> None:
    """Guards the guard. A note on every run is a note nobody reads."""
    moving = {
        "per_detector_pre": {"a": 0.99, "b": 0.90},
        "per_detector_post": {"a": 0.30, "b": 0.40},
    }
    assert _pinned_note(moving) == []


def test_a_run_where_nothing_moved_says_nothing() -> None:
    """There is no contradiction to flag when the headline and the detail agree — the loop really
    did achieve nothing, and the report should not soften that."""
    stuck = {
        "per_detector_pre": {"a": 0.99, "b": 0.90},
        "per_detector_post": {"a": 0.985, "b": 0.899},
    }
    assert _pinned_note(stuck) == []


def test_a_baseline_only_run_says_nothing() -> None:
    assert _pinned_note({"per_detector_pre": {"a": 0.9}, "per_detector_post": None}) == []
    assert _pinned_note({}) == []


def test_the_threshold_is_far_below_the_gap_it_must_separate() -> None:
    """0.376 moved against 0.0000 stuck. Any bar between them works; this pins that the shipped one
    is not accidentally above the movement it exists to detect."""
    assert 0.0 < _PINNED_DELTA < 0.376
