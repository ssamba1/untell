"""Tests for the benchmark baseline strategies — offline, no network."""
from __future__ import annotations

import pytest

from eval.baselines import (
    STRATEGIES,
    LoopResult,
    full_loop,
    noop,
    rewrite,
    single_pass,
)


def test_noop_returns_input_unchanged():
    text = "This is some sample text with several words in each sentence. It has two sentences total."
    res = noop(text, tier="lite")
    assert res.text == text
    assert res.iterations == 0
    assert res.similarity == 1.0


def test_single_pass_rewrites_and_scores():
    text = "Furthermore, artificial intelligence has transformed industries. Moreover, it improves efficiency overall."
    res = single_pass(text, tier="lite")
    assert isinstance(res, LoopResult)
    assert res.iterations == 1
    assert res.text != text  # should have been rewritten
    assert 0.0 <= res.pre["max"] <= 1.0
    assert 0.0 <= res.post["max"] <= 1.0
    assert 0.0 <= res.similarity <= 1.0


def test_full_loop_runs_and_may_improve():
    text = "Furthermore, artificial intelligence has transformed industries. Moreover, it improves efficiency overall."
    res = full_loop(text, tier="lite", max_iters=3)
    assert isinstance(res, LoopResult)
    assert 1 <= res.iterations <= 3
    assert 0.0 <= res.similarity <= 1.0
    assert hasattr(res, "history") and len(res.history) >= 1


def test_rewrite_function_strips_transitions():
    text = "Moreover, this is a test. Furthermore, it works well. Overall, the results are good."
    result = rewrite(text, strength=1.0)
    # Transitions should be gone at high strength
    for bad in ("Moreover,", "Furthermore,", "Overall,"):
        assert bad not in result, f"Expected {bad} to be removed, got: {result}"


def test_rewrite_function_empty():
    assert rewrite("", strength=0.5) == ""


def test_rewrite_function_varying_strength():
    """Higher strength should produce more aggressive rewrites (more sentence merges)."""
    text = "Furthermore, this is a test. Moreover, it has multiple sentences. Additionally, it counts as three for now."
    weak = rewrite(text, strength=0.1)
    strong = rewrite(text, strength=1.0)
    # At strength 1.0, adjacent sentences get merged into compound sentences.
    # At strength 0.1, sentences stay separate.
    assert weak != strong, f"Expected different outputs: weak={weak!r} strong={strong!r}"


def test_all_strategies_registered():
    for name in ("noop", "single_pass", "full_loop", "api_loop"):
        assert name in STRATEGIES, f"Missing strategy: {name}"
        assert callable(STRATEGIES[name])


@pytest.mark.parametrize("name", ["noop", "single_pass", "full_loop"])
def test_each_strategy_returns_loop_result(name):
    text = "This is some text with formulaic transitions. Moreover, it represents a test."
    fn = STRATEGIES[name]
    res = fn(text, tier="lite")
    assert isinstance(res, LoopResult)
    assert 0.0 <= res.similarity <= 1.0


def test_strength_zero_changes_no_content():
    """`strength=0.0` is the control at the bottom of a sweep and must not rewrite anything.

    The selection used to read `if strength >= 0.5 or idx % 2 == 0`, which is not proportional to
    anything: every strength below 0.5 stripped exactly half the sentences, so 0.0, 0.1 and 0.4
    produced byte-identical output and there was no untouched control at all.

    Compared on normalised whitespace, because splitting into sentences and rejoining collapses
    newlines — see the `rewrite` docstring.
    """
    from eval.baselines import rewrite

    text = (
        "Moreover, artificial intelligence has transformed industry.\n\n"
        "Furthermore, organizations leverage these tools.\n\n"
        "In conclusion, the impact continues to grow."
    )
    assert " ".join(rewrite(text, strength=0.0).split()) == " ".join(text.split())
    for word in ("Moreover", "Furthermore", "In conclusion"):
        assert word in rewrite(text, strength=0.0), f"{word} was stripped at strength 0"


def test_transition_stripping_is_monotone_in_strength():
    """More strength must never strip fewer openers."""
    from eval.baselines import rewrite

    text = " ".join(
        f"{opener}, this is sentence number {i} in the paragraph."
        for i, opener in enumerate(
            ["Moreover", "Furthermore", "Additionally", "Overall", "Therefore", "Thus"]
        )
    )
    survivors = [
        sum(1 for w in ("Moreover", "Furthermore", "Additionally", "Overall", "Therefore", "Thus")
            if w in rewrite(text, strength=s))
        for s in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
    ]
    assert survivors == sorted(survivors, reverse=True), f"not monotone: {survivors}"
    assert survivors[0] == 6, "strength 0 stripped an opener"
    assert survivors[-1] == 0, "strength 1 left an opener in place"
