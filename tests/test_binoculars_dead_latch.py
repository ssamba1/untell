"""BinocularsDetector _dead-latch and load-failure guards.

Every other supervised adapter has:
    1. A class-level ``_dead = False`` flag that prevents retrying a failed model load.
    2. A try/except in ``score()`` that sets ``_dead = True`` and logs before re-raising.

BinocularsDetector was the lone adapter without either, so a ``_load()`` failure
(network error, CUDA error, disk full) would:
    * Re-attempt loading two 7B Falcon models on EVERY subsequent ``score()`` call.
    * Log nothing — a silent retry storm costing 14 GB of network / VRAM pressure.

This is the exact failure the task description calls out:
    "radar and local_judge were just given the _dead flag the others had
     (a failed load retried once per document, forever)"
"""

from __future__ import annotations

import pytest


def test_binoculars_has_dead_class_attribute():
    """_dead must exist as a class attribute before any instance is created.

    If it's missing, ``score()`` has no way to check it and the guard cannot
    short-circuit the expensive load on the second call.
    """
    from untell.detectors.binoculars import BinocularsDetector

    assert hasattr(BinocularsDetector, "_dead"), (
        "BinocularsDetector has no _dead class attribute. "
        "A _load() failure will retry the 14 GB model download on every score() call "
        "with no warning — the exact pattern fixed in radar and local_judge."
    )


def test_binoculars_dead_latch_starts_false():
    """Sanity: the latch starts False so available instances can actually score."""
    from untell.detectors.binoculars import BinocularsDetector

    # Reset in case another test dirtied it.
    BinocularsDetector._dead = False
    assert BinocularsDetector._dead is False


def test_binoculars_load_failure_sets_dead_latch(monkeypatch):
    """After _load() raises, _dead must be True so subsequent calls short-circuit.

    Without this, the two 7B Falcon models are re-downloaded / re-initialised on
    every score() call after the first failure.
    """
    from untell.detectors.binoculars import BinocularsDetector

    BinocularsDetector._dead = False
    BinocularsDetector._observer = None  # ensure _load() is reached

    d = BinocularsDetector()

    # Patch available() so the empty-or-unavailable guard does not fire.
    monkeypatch.setattr(BinocularsDetector, "available", lambda self: True)

    def _boom():
        raise RuntimeError("CUDA out of memory")

    # Bind as an instance attribute so it shadows the class method without
    # changing self's signature (Python calls instance attrs directly).
    d._load = _boom

    with pytest.raises(RuntimeError, match="CUDA out of memory"):
        d.score("Some real text that is long enough to score.")

    assert BinocularsDetector._dead is True, (
        "score() must set _dead=True after _load() raises so the next call "
        "skips the model reload instead of retrying it."
    )


def test_binoculars_dead_latch_prevents_second_load(monkeypatch):
    """Once _dead is True, score() must return None without calling _load()."""
    from untell.detectors.binoculars import BinocularsDetector

    BinocularsDetector._dead = True

    load_calls = []

    def _should_not_be_called():
        load_calls.append(1)
        raise AssertionError("_load() was called after _dead=True")

    d = BinocularsDetector()
    d._load = _should_not_be_called
    monkeypatch.setattr(BinocularsDetector, "available", lambda self: True)

    result = d.score("Some text.")
    assert result is None, f"expected None when _dead=True, got {result!r}"
    assert not load_calls, "_load() must not be called when _dead is True"

    # cleanup
    BinocularsDetector._dead = False
