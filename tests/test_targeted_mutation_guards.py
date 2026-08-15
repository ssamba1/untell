"""Killing tests for targeted.py mutation survivors (2026-08-14 sweep).

  line 118  boundary: < -> <=      per-sentence min_score gate.
  line 210  boundary: < -> <=      single-sentence min_score gate.
  line 216  logic: != -> ==        sentinel-integrity check.

Killed here. The 11 pre-killed survivors (93 x2, 105, 128, 148 x2, 151, 157, 222)
were caught by the existing targeted suite.
"""

from __future__ import annotations

from untell.rewriter.targeted import TargetedRewriter


class TestSingleSentenceGate:
    """Survivor 210 — single-sentence path: `before[0] < self.min_score` -> `<=`.

    A single sentence scoring EXACTLY at min_score must reach the inner rewriter
    (it is targetable). The mutation skips it, returning the text untouched."""

    def test_exactly_at_min_score_reaches_inner(self, monkeypatch) -> None:
        rw = TargetedRewriter()
        rw.min_score = 0.30
        calls = []

        class _Inner:
            def rewrite(self, text, score_result, threshold):
                calls.append(text)
                return text + " REWRITTEN"

        rw._inner = _Inner()
        monkeypatch.setattr(
            "untell.scripts.score.score_text",
            lambda text, tier: {"max": 0.30, "mean": 0.30, "tier": tier},
        )
        monkeypatch.setattr(
            "untell.rewriter.targeted.selection_key",
            lambda s: (s["max"], s["mean"]),
        )
        rw.rewrite("some text here", {"tier": "lite"}, threshold=0.30)
        assert calls, "single sentence at min_score must reach the inner rewriter"


class TestMultiSentenceGate:
    """Survivor 118 — per-sentence gate: a sentence exactly AT min_score is
    targetable; the mutation skips it, leaving the sentence untouched."""

    def test_sentence_at_min_score_is_targeted(self, monkeypatch) -> None:
        rw = TargetedRewriter()
        rw.min_score = 0.30
        calls = []

        class _Inner:
            def rewrite(self, text, score_result, threshold):
                calls.append(text)
                return text

        rw._inner = _Inner()
        monkeypatch.setattr(
            "untell.scripts.score.score_text",
            lambda text, tier: {"max": 0.30, "mean": 0.30, "tier": tier},
        )
        monkeypatch.setattr(
            "untell.rewriter.targeted.selection_key",
            lambda s: (s["max"], s["mean"]),
        )
        rw.rewrite(
            "First sentence here. Second sentence here too.",
            {"tier": "lite"},
            threshold=0.30,
        )
        # each sentence at min_score must be passed to the inner individually
        assert any("First sentence" in c for c in calls), calls
        assert any("Second sentence" in c for c in calls), calls


class TestSentinelIntegrity:
    """Survivor 216 — `Counter(cand) != Counter(stripped)` mutated to `==`.

    A candidate that loses sentinels is rejected. The mutation accepts it,
    letting silent fact loss through."""

    def test_sentinel_loss_rejected(self, monkeypatch) -> None:
        rw = TargetedRewriter()
        rw.min_score = 0.0

        class _Inner:
            def rewrite(self, text, score_result, threshold):
                return text.replace("\x00LOCKED\x00", "")

        rw._inner = _Inner()
        monkeypatch.setattr(
            "untell.scripts.score.score_text",
            lambda text, tier: {"max": 0.9, "mean": 0.9, "tier": tier},
        )
        monkeypatch.setattr(
            "untell.rewriter.targeted.selection_key",
            lambda s: (s["max"], s["mean"]),
        )
        out = rw.rewrite("keep \x00LOCKED\x00 this", {"tier": "lite"}, threshold=0.30)
        assert out == "keep \x00LOCKED\x00 this"

    def test_sentinel_preserving_candidate_adopted(self, monkeypatch) -> None:
        # With the == mutation, a VALID candidate (sentinels preserved) is
        # REJECTED because the counters are equal. Original accepts it.
        rw = TargetedRewriter()
        rw.min_score = 0.0

        class _Inner:
            def rewrite(self, text, score_result, threshold):
                return text + " REWRITTEN"  # preserves the sentinel

        rw._inner = _Inner()
        calls = {"n": 0}

        def _score(text, tier):
            # original scores 0.9; the rewritten candidate scores 0.5 (improvement)
            calls["n"] += 1
            if "REWRITTEN" in text:
                return {"max": 0.5, "mean": 0.5, "tier": tier}
            return {"max": 0.9, "mean": 0.9, "tier": tier}

        monkeypatch.setattr("untell.scripts.score.score_text", _score)
        monkeypatch.setattr(
            "untell.rewriter.targeted.selection_key",
            lambda s: (s["max"], s["mean"]),
        )
        out = rw.rewrite("keep \x00LOCKED\x00 this", {"tier": "lite"}, threshold=0.30)
        assert "REWRITTEN" in out, f"valid sentinel-preserving candidate must be adopted: {out!r}"
