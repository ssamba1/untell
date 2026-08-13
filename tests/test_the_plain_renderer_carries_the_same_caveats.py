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


def _run_renderer(*, rich: bool, warning: str | None) -> str:
    """Render through `print_humanize_result` with the rich path forced on or off."""
    import contextlib
    import io

    import untell.rich_output as module

    previous = module._RICH
    module._RICH = rich and previous  # never claim rich is available when it is not installed
    buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(buffer):
            module.print_humanize_result(
                original="Moreover, the framework leverages robust methodologies.",
                final="The structure uses solid methods.",
                pre_score={"max": 0.86, "detectors": {"perplexity_burstiness": 0.86}},
                post_score={"max": 0.21, "detectors": {"perplexity_burstiness": 0.21}},
                iterations=1,
                stopped="passed",
                warning=warning,
                tells_before=5,
                tells_after=0,
            )
    finally:
        module._RICH = previous
    return buffer.getvalue()


def test_both_renderers_print_the_caveat_they_are_handed():
    """Parity, asserted by RENDERING rather than by reading the source.

    This used to be `assert "warning" in inspect.getsource(print_humanize_result)`, which passes as
    long as EITHER branch mentions it — and only the rich branch did. The plain branch returned
    before reaching the caveat, so it was dropped, and the check that existed to prevent exactly
    that drift could not see it.

    The omission mattered most on the path a plain `pip install untell` takes: `rich` is an optional
    extra, and `run.py`'s `except ImportError` fallback to `_render` (which does print the caveat)
    is unreachable, because importing `rich_output` always succeeds and merely sets `_RICH` False.
    """
    marker = "SENTINEL-CAVEAT-TEXT"
    plain = _run_renderer(rich=False, warning=marker)
    assert marker in plain, f"the plain renderer dropped the caveat it was given: {plain!r}"

    pytest.importorskip("rich")
    rich_out = _run_renderer(rich=True, warning=marker)
    assert marker in rich_out, f"the rich renderer dropped the caveat it was given: {rich_out!r}"


def test_neither_renderer_invents_a_caveat():
    """Guards the guard. A renderer that always printed a NOTE line would satisfy the test above
    while telling every user their number needs qualifying."""
    plain = _run_renderer(rich=False, warning=None)
    assert "NOTE:" not in plain, f"plain renderer printed a caveat it was not given: {plain!r}"


def test_both_renderers_show_the_tell_counts():
    """The other half of the parity claim, also by rendering."""
    plain = _run_renderer(rich=False, warning=None)
    assert "AI tells: 5 -> 0" in plain, (
        f"the plain renderer shows no tell counts: {plain!r}"
    )
