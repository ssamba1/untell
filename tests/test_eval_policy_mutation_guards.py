"""Killing tests for eval/eval_policy.py mutation survivors (2026-08-14 sweep).

  line 42   logic: and -> or        scored flag (both sides must score).
  line 68   boundary: < -> <=       bypass count at exact threshold.

Killed here via _eval with stubbed score_text/similarity/rewriter. The other
survivors (85 argparse default, 104/116/123 return codes + availability gates)
are constants — annotated in survivors.md.
"""

from __future__ import annotations

import pytest

from eval import eval_policy as E


class TestScoredFlag:
    """Survivor eval_policy.py:42 — `pre scored and post scored` -> `or`.

    A row where ONLY ONE side scored must not be marked scored (a dead detector
    on either side makes the numbers meaningless). The mutation marks it scored,
    letting a dead stack look like a working policy."""

    def test_one_sided_scored_is_not_scored(self, monkeypatch) -> None:
        from eval import eval_policy as EP

        class _RW:
            name = "fake"

            def rewrite(self, s, sr, threshold):
                return s

        calls = {"n": 0}

        def _score(text, tier):
            calls["n"] += 1
            # pre is scored (max real), post is UNSCORED (max 0.0 placeholder)
            if calls["n"] % 2 == 1:
                return {"max": 0.5, "scored": True}
            return {"max": 0.0, "scored": False}

        monkeypatch.setattr("untell.scripts.score.score_text", _score)
        monkeypatch.setattr("untell.scripts.quality.similarity", lambda a, b: 1.0)
        rows = EP._eval(_RW(), ["sample text"], "lite", 0.3)
        assert rows[0]["scored"] is False, rows[0]


class TestBypassThreshold:
    """Survivor eval_policy.py:68 — `post < threshold` -> `<=` in the bypass count.

    A post score EXACTLY at the threshold is not a bypass (strict <). The
    mutation counts it, inflating the bypass rate."""

    def test_exact_threshold_not_bypass(self) -> None:
        rows = [
            {"pre": 0.5, "post": 0.50, "sim": 1.0, "scored": True},  # exactly at 0.5
            {"pre": 0.5, "post": 0.40, "sim": 1.0, "scored": True},  # below 0.5
        ]
        line = E._summary("fake", rows, 0.5)
        # only the 0.40 row bypasses -> 1/2 = 50%
        assert "50%" in line, line
