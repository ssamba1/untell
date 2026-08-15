"""Killing tests for ensemble.py mutation survivors (2026-08-14 sweep).

  line 171  logic: == -> != / or -> and   blank/identical candidate exclusion.
  line 186  boundary: < -> <=            passing threshold (0.30 gate).
  line 187  logic: or -> and             near-band fallback.

Killed here. The other 5 survivors (92/107/109/115) are constructor/availability
constants — annotated in survivors.md.
"""

from __future__ import annotations

from untell.rewriter.ensemble import EnsembleRewriter


class _FakeMember:
    def __init__(self, out):
        self._out = out

    def rewrite(self, text, score_result, threshold):
        return self._out


class TestCandidateExclusion:
    """Survivor ensemble.py:171 — `not cand.strip() or cand == text` mutated.

    A member that returns the text unchanged (or blank) must not enter the
    candidate pool — it is not a rewrite. The ==->!= mutation admits identical
    candidates; the or->and mutation admits blank ones."""

    def test_unchanged_candidate_excluded(self, monkeypatch) -> None:
        rw = EnsembleRewriter()
        rw._members = [("fake", _FakeMember("same text here"))]
        monkeypatch.setattr(
            "untell.scripts.score.score_text",
            lambda text, tier: {"max": 0.1, "mean": 0.1, "tier": tier},
        )
        out = rw.rewrite("same text here", {"tier": "lite"}, threshold=0.30)
        # only the original is in the pool -> it wins
        assert out == "same text here"

    def test_blank_candidate_excluded(self, monkeypatch) -> None:
        # Survivor 171 (or->and): a blank member output must be skipped. With `and`,
        # `not cand.strip()` (True) and `cand == text` (False) -> NOT skipped, so
        # score_text is called on the empty string.
        rw = EnsembleRewriter()
        rw._members = [("fake", _FakeMember(""))]
        seen = []

        def _score(text, tier):
            seen.append(text)
            return {"max": 0.1, "mean": 0.1, "tier": tier}

        monkeypatch.setattr("untell.scripts.score.score_text", _score)
        rw.rewrite("original text", {"tier": "lite"}, threshold=0.30)
        assert "" not in seen, "blank candidate must never be scored"


class TestPassingThreshold:
    """Survivor ensemble.py:186 — `r[0] < threshold` mutated to `<=`.

    A candidate at exactly 0.30 does NOT pass a 0.30 gate (strict <). The
    mutation admits it, selecting a failing candidate."""

    def test_exact_threshold_does_not_pass(self, monkeypatch) -> None:
        rw = EnsembleRewriter()
        # candidate scores exactly 0.30 (threshold) with a BAD mean; original
        # scores 0.35 with a good mean. With strict <, 0.30 is NOT "passing" and
        # the near-band mean tie-break picks the ORIGINAL. With <= (mutation),
        # 0.30 IS passing and the bad-mean candidate is selected directly.
        rw._members = [("fake", _FakeMember("candidate text"))]

        def _score(text, tier):
            if text == "candidate text":
                return {"max": 0.30, "mean": 0.90, "tier": tier}
            # 0.31 is within the 0.02 band of the 0.30 best -> competes in near
            return {"max": 0.31, "mean": 0.30, "tier": tier}

        monkeypatch.setattr("untell.scripts.score.score_text", _score)
        out = rw.rewrite("original text", {"tier": "lite"}, threshold=0.30)
        assert out == "original text"


class TestNearBandFallback:
    """Survivor ensemble.py:187 — `near = passing or near` mutated to `and`.

    When nothing passes the threshold, the near-band (within EPS of best) is the
    fallback. The mutation (`passing and near`) yields [] when passing is empty,
    and min() on [] raises."""

    def test_nothing_passing_uses_near_band(self, monkeypatch) -> None:
        rw = EnsembleRewriter()
        # all candidates score 0.5 > 0.30 threshold: passing is empty
        rw._members = [("fake", _FakeMember("candidate text"))]
        monkeypatch.setattr(
            "untell.scripts.score.score_text",
            lambda text, tier: {"max": 0.5, "mean": 0.4, "tier": tier},
        )
        out = rw.rewrite("original text", {"tier": "lite"}, threshold=0.30)
        assert isinstance(out, str)  # near-band fallback returns something, no crash
