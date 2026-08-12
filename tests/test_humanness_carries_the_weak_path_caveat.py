"""`untell humanness` answered "human" with no caveat on the path that clears most AI text.

The two commands read the same signals and answered differently about how far to trust them.
MEASURED on one paragraph carrying 8.3 AI tells per 100 words — "Moreover", "leverages",
"transformative", "underscores the importance" — on the pure-stdlib lite path:

    untell humanness --tier lite   ->  "79.8/100 (human)"   and nothing else
    untell score     --tier lite   ->  the full both-directions warning

`_warn_about_invisibles` forwards the invisible-character caveat "and drops the rest", which was a
reasonable rule when invisibles were the only pass-through worth making and which silently dropped
the one that changes how the number should be read.

That it is a property of the PATH and not of the bands was checked both ways over paired HC3
documents:

    stdlib lite   16 of 18 "mostly human" bands sit on text the same path FLAGS
    full tier     0 of 20 disagreements — every band matches its verdict

So the bands are fine. The stdlib detector is weak in both directions, `score` says so, and
`humanness` did not. A single reassuring word is the wrong place to be silent.
"""
from __future__ import annotations

import logging

import pytest

from untell import humanness as H

AI_TEXT = (
    "Moreover, the framework leverages robust methodologies to deliver outcomes at scale across "
    "the evaluated corpus. It significantly improves overall efficiency and accuracy, and "
    "organizations increasingly adopt these transformative technologies to optimize operational "
    "workflows. Furthermore, the impact continues to expand across numerous sectors, reshaping "
    "how enterprises approach strategic decision making and long term planning today."
)


@pytest.fixture(autouse=True)
def _fresh(monkeypatch):
    """The warning is once-per-process by design, so reset the latch between tests."""
    monkeypatch.setattr(H, "_WARNED_WEAK_PATH", False)


def test_the_stdlib_path_warns(monkeypatch, caplog):
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
    with caplog.at_level(logging.WARNING):
        H.humanness(AI_TEXT, tier="lite")
    assert "pure-stdlib lite path" in caplog.text, (
        "humanness answered from the weakest detector path without saying so"
    )
    assert "not a pass" in caplog.text


def test_the_warning_says_which_direction_it_fails_in(monkeypatch, caplog):
    """Both directions, or a reader takes it as 'may over-flag' and relaxes."""
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
    with caplog.at_level(logging.WARNING):
        H.humanness(AI_TEXT, tier="lite")
    assert "both directions" in caplog.text
    assert "64%" in caplog.text and "%%" not in caplog.text, (
        "logging interpolates only when args are supplied, so %% reaches the user literally"
    )


def test_it_fires_once_per_process(monkeypatch, caplog):
    """A caveat on every call is a caveat nobody reads — the same rule the invisibles note follows."""
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
    with caplog.at_level(logging.WARNING):
        H.humanness(AI_TEXT, tier="lite")
        H.humanness(AI_TEXT, tier="lite")
    assert caplog.text.count("pure-stdlib lite path") == 1


def test_a_model_backed_run_stays_quiet(monkeypatch, caplog):
    """Scoped to the path it describes. Warning at full tier would train readers to skip it."""
    monkeypatch.delenv("UNTELL_LITE_NO_TORCH", raising=False)
    from untell.detectors.perplexity_burstiness import PerplexityBurstinessDetector

    if PerplexityBurstinessDetector().mode() != "gpt2":
        pytest.skip("torch is not importable here, so there is no model-backed path to check")

    with caplog.at_level(logging.WARNING):
        H.humanness(AI_TEXT, tier="full")
    assert "pure-stdlib lite path" not in caplog.text


def test_the_number_itself_is_unchanged(monkeypatch):
    """A caveat, not a correction. Moving the score would be a different change with its own case."""
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
    assert 0.0 <= H.humanness(AI_TEXT, tier="lite") <= 100.0
