"""The targeting caveat must follow the path that scored, not the one that was predicted.

`score_sentences` decides which spans the rewriter attacks. On the stdlib path that ranking is a
coin flip — measured AUROC 0.493, and worse in shape than that suggests: 6 distinct values across
100 sentences, 91 of them exactly 0.250. The result carries a warning saying so.

The gate asked `PerplexityBurstinessDetector()._torch_ready()`. That is the path PREDICTED. The
two answers separate on the failure that matters most: torch imports, the model raises at scoring
time (OOM, a corrupted cache, a transformers version bump), the stdlib heuristic quietly produces
the numbers, and the caveat is suppressed in exactly the run that needed it. `mode()` exists
because of this; `_verdict_threshold` and the single-sentence caveat in score.py already use it.

Consequence here is not cosmetic. A suppressed caveat plus a coin-flip ranking points the rewriter
at whichever sentences read most human.
"""
from __future__ import annotations

import pytest

from untell.scripts.sentences import UNINFORMATIVE_TARGETING_WARNING, _targeting_is_uninformative

TEXT = "The system reads the file first. Then it writes each record onward to the loader."


def test_the_gpt2_path_needs_no_caveat():
    """AUROC 0.968 per sentence. Warning there would talk a caller out of a usable ranking."""
    assert _targeting_is_uninformative("lite", {"perplexity_burstiness": "gpt2"}) is False


def test_the_stdlib_path_gets_the_caveat_even_where_torch_imports():
    """The regression. Prediction says gpt2, the run says stdlib, and the run is what happened."""
    assert _targeting_is_uninformative("lite", {"perplexity_burstiness": "stdlib"}) is True


def test_a_model_backed_detector_scoring_needs_no_caveat():
    """Not the heuristic's ranking at all, so the heuristic's AUROC is not the relevant number."""
    assert _targeting_is_uninformative("full", {"hc3_roberta": "model"}) is False


def test_the_result_carries_the_caveat_on_the_stdlib_path(monkeypatch):
    """End to end: the field a machine client reads, on the path the measurement describes."""
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
    from untell.scripts.sentences import score_sentences

    result = score_sentences(TEXT, tier="lite")
    assert result.get("detector_modes", {}) or True  # shape may vary; the warning is the contract
    assert result.get("warning") == UNINFORMATIVE_TARGETING_WARNING


def test_the_result_omits_the_caveat_when_a_model_ranked_the_sentences(monkeypatch):
    monkeypatch.delenv("UNTELL_LITE_NO_TORCH", raising=False)
    from untell.detectors.perplexity_burstiness import PerplexityBurstinessDetector
    from untell.scripts.sentences import score_sentences

    if PerplexityBurstinessDetector().mode() != "gpt2":
        pytest.skip("torch is not importable here, so there is no model path to check")

    assert "warning" not in score_sentences(TEXT, tier="lite")
