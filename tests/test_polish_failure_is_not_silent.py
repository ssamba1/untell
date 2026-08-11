"""A persistently broken polish stage must say so once, not degrade output in silence.

`except Exception: pass` around the polish block is right for a transient failure — polish is
optional and the unpolished candidate is a valid answer. It is wrong for a persistent one: a
missing similarity model or a broken substitution table disables the stage on every call, output
quality drops, and nothing anywhere says so. That is the same silent-no-op shape as the composite
selector that shipped disabled.
"""

from __future__ import annotations

import logging

import pytest

import untell.attacks as attacks
import untell.scripts.run as run_module
from untell.scripts.run import untell_text

TEXT = (
    "Moreover, the framework leverages robust methodologies to deliver outcomes at scale. "
    "Furthermore, it significantly improves overall efficiency and accuracy across the corpus."
)


@pytest.fixture
def broken_polish(monkeypatch: pytest.MonkeyPatch):
    """Break ONLY run.py's polish call.

    `surgical_substitute` is also the composite rewriter's second stage, called with `max_subs`
    and `prefer_tells`. Raising on every call aborts the rewrite before the polish block is
    reached — which is how an earlier version of this test measured nothing and passed. The
    polish call is the one taking exactly `tier` and `threshold`.
    """
    original = attacks.surgical_substitute

    def only_polish_explodes(*args, **kwargs):
        if set(kwargs) == {"tier", "threshold"}:
            raise RuntimeError("polish exploded")
        return original(*args, **kwargs)

    monkeypatch.setattr(attacks, "surgical_substitute", only_polish_explodes)
    run_module._POLISH_FAILED.clear()
    yield
    run_module._POLISH_FAILED.clear()


def _run(**kw):
    return untell_text(
        TEXT, tier="lite", threshold=0.0, max_iters=1, rewriter="composite", polish=True, **kw
    )


def test_a_broken_polish_stage_warns(broken_polish, caplog: pytest.LogCaptureFixture):
    with caplog.at_level(logging.WARNING, logger="untell.scripts.run"):
        _run()
    assert "polish stage failed" in caplog.text
    assert "polish exploded" in caplog.text, "the warning must name the cause"


def test_it_warns_once_not_every_call(broken_polish, caplog: pytest.LogCaptureFixture):
    """A per-call warning on a persistent failure is noise, and noise is how a warning is missed."""
    with caplog.at_level(logging.WARNING, logger="untell.scripts.run"):
        for _ in range(3):
            _run()
    assert caplog.text.count("polish stage failed") == 1


def test_the_run_still_returns_usable_text(broken_polish):
    """Polish is optional: its failure must not cost the caller their rewrite."""
    result = _run()
    assert result["final"].strip()


def test_a_healthy_polish_stage_says_nothing(caplog: pytest.LogCaptureFixture):
    """Guards the guard — a warning on every healthy run would be indistinguishable from noise."""
    run_module._POLISH_FAILED.clear()
    with caplog.at_level(logging.WARNING, logger="untell.scripts.run"):
        _run()
    assert "polish stage failed" not in caplog.text


def test_polish_is_off_by_default():
    """Pins the premise of the tests above: the stage only runs when asked for."""
    import inspect

    assert inspect.signature(untell_text).parameters["polish"].default is False
