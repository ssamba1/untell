"""A published number needs the build it came from, not just the command.

The README's composite column — mean max 0.778, `hc3_roberta` 0.710 — stopped reproducing when
`structural.py`'s draws were seeded, and the reproduce command printed beside it still reads exactly
the same. Nothing in the figure said which build produced it, so the drift stayed invisible until
someone re-ran it by hand and got 0.9994.

The audit already requires every measured number to state a source, and accepts `MEASURED`, `n=6` or
`Result 12`. None of those pins a build, and a randomized rewriter's output number needs one.

Stamping it on every run is cheaper than policing the prose afterwards, and it makes the next
occurrence self-evident: two numbers with different commits are two measurements, not a
contradiction.
"""

from __future__ import annotations

import logging
import subprocess

import pytest

from eval.ceiling import _code_state, _render

BASE = {
    "tier": "full",
    "threshold": 0.3,
    "best_of": 3,
    "n": 6,
    "rewriter": "composite",
    "rewriter_available": True,
    "corpus": "hc3",
    "corpus_mean_words": 185.5,
    "pre_flagged_rate": 1.0,
    "pre_mean_max": 0.9997,
    "post_flagged_rate": 1.0,
    "post_mean_max": 0.9994,
    "rewrote": 18,
    "repeats": 1,
    "per_detector_pre": {"hc3_roberta": 0.9992},
    "per_detector_post": {"hc3_roberta": 0.9992},
}


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


def test_the_header_carries_a_commit() -> None:
    header = _render(BASE).splitlines()[0]
    assert "commit=" in header, header


def test_the_stamp_matches_git() -> None:
    """Premise plus correctness: in a checkout it must be the real short hash, not a placeholder."""
    out = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30
    )
    if out.returncode != 0:  # not a checkout; the fallback path is covered below
        pytest.skip("not a git checkout")
    assert _code_state().startswith(out.stdout.strip())


def test_uncommitted_work_is_marked() -> None:
    """A number measured against edited files is not a number anyone can re-derive from the hash,
    and saying so costs one word."""
    dirty = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30
    )
    if dirty.returncode != 0:
        pytest.skip("not a git checkout")
    assert ("+dirty" in _code_state()) == bool(dirty.stdout.strip())


def test_a_missing_git_does_not_break_the_report(monkeypatch) -> None:
    """A provenance stamp must never break the measurement it labels. A number from a pip install
    with no checkout is still a number."""
    def _boom(*args, **kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr(subprocess, "run", _boom)
    assert _code_state() == "unknown"
    assert "commit=unknown" in _render(BASE).splitlines()[0]


def test_an_explicit_commit_on_the_result_wins() -> None:
    """So a stored result renders with the build it was measured at, not the build reading it."""
    header = _render({**BASE, "commit": "abc1234"}).splitlines()[0]
    assert "commit=abc1234" in header
