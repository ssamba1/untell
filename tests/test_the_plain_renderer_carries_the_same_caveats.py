"""The install with fewer dependencies was also the one told less about its own answer.

`rich` is an EXTRA, so `_render` is what `pip install untell` prints. The rich table shows an
"AI tells" row and the score's `warning`; this path showed neither — a number with none of the
caveats attached to it.

MEASURED on the stdlib path before the fix, the whole plain output was:

    tier=lite  iterations=1  stopped=passed
    max P(AI): 0.534 -> 0.042  (threshold 0.3)
    similarity: 0.804 (bar 0.76, embedding)
    meaning gate: nli
    per-detector (pre -> post): ...

No mention that this path flags 64% of human text, none that the input was too short for a
verdict, and no tell counts. All three were in the result dict the renderer was handed.

The meaning-gate warning was already there, which is what made the omission easy to miss: the
page looked like it warned about things.
"""
from __future__ import annotations

import pytest

from untell.scripts.run import _render


def _result(**overrides) -> dict:
    base = {
        "tier": "lite",
        "iterations": 1,
        "stopped": "passed",
        "pre": {"max": 0.534, "threshold": 0.30, "detectors": {"perplexity_burstiness": 0.534}},
        "post": {"max": 0.042, "threshold": 0.30, "detectors": {"perplexity_burstiness": 0.042}},
        "similarity": 0.804,
        "sim_bar": 0.76,
        "quality_metric": "embedding",
        "meaning_gate": "nli",
        "final": "the rewritten text",
        "tells_before": 2,
        "tells_after": 0,
    }
    base.update(overrides)
    return base


def test_the_tell_counts_are_shown():
    out = _render(_result())
    assert "AI tells" in out, out
    assert "2 -> 0" in out and "-2" in out, out


def test_the_score_warning_is_shown():
    out = _render(_result(warning="lite tier on the stdlib path. Weak evidence in both directions."))
    assert "stdlib path" in out, out
    assert "NOTE" in out, "the caveat needs a label, or it reads as part of the result"


def test_nothing_is_invented_when_the_result_has_neither():
    """A renderer that prints a row it was not given is worse than one that omits it."""
    result = _result()
    del result["tells_before"]
    del result["tells_after"]

    out = _render(result)
    assert "AI tells" not in out
    assert "NOTE" not in out


@pytest.mark.parametrize("bad", [None, "3", 2.5])
def test_a_non_integer_count_is_skipped_rather_than_formatted(bad):
    """`{after - before:+d}` raises on a string or a float, and a renderer must not take the run down."""
    out = _render(_result(tells_before=bad, tells_after=0))
    assert "AI tells" not in out


def test_the_meaning_gate_warning_still_appears():
    """It was already there. The point is that its presence made the other omissions easy to miss."""
    out = _render(_result(meaning_gate="similarity-only (NLI unavailable)"))
    assert "did NOT run" in out


def test_the_rich_path_shows_the_same_two_things():
    """Parity, so the two renderers cannot drift apart again in either direction."""
    pytest.importorskip("rich")
    import inspect

    from untell.rich_output import print_humanize_result

    source = inspect.getsource(print_humanize_result)
    assert "AI tells" in source
    assert "warning" in source
