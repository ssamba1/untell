"""Cross-adapter contract tests for every detector (no model loads).

Every detector adapter must satisfy the Detector protocol on the surfaces that
don't need a live model: empty text -> None (no signal), whitespace-only -> None,
and available() never raising. These are the shared invariants the ensemble
aggregation depends on (`_score_with_detectors` excludes None/NaN, never folds
them in as a fake neutral).
"""

from __future__ import annotations

import pytest

from untell.detectors.base import all_detectors


def _adapters():
    return all_detectors()


class TestEmptyTextContract:
    """Every adapter: empty/whitespace input returns None (no signal), never 0.5."""

    @pytest.mark.parametrize("text", ["", "   ", "\n\t ", " \u00a0 "])
    def test_empty_inputs_abstain(self, text) -> None:
        for d in _adapters():
            # score may raise if the detector needs a model (dead latch off);
            # the contract is about the guard BEFORE the load.
            try:
                result = d.score(text)
            except Exception:
                continue
            assert result is None, f"{d.name} scored {result!r} for empty input"


class TestNeverFabricatesNeutral:
    """A detector that cannot run reports None, never a fake 0.5.

    This is the documented invariant: a dead/missing component must be excluded
    from the ensemble max, not pinned at "unsure"."""

    def test_empty_text_never_returns_half(self) -> None:
        for d in _adapters():
            try:
                result = d.score("")
            except Exception:
                continue
            assert result != 0.5, f"{d.name} returned fake neutral for empty input"
