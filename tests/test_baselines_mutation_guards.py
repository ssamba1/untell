"""Killing tests for eval/baselines.py mutation survivors (2026-08-14 sweep).

  line 190  logic: and -> or / boundaries  greedy acceptance gate (full_loop).
  line 230  identity: is not -> is         rewriter dispatch (api_loop).
  line 240  logic: and -> or               greedy acceptance gate (api_loop).

Killed here via monkeypatched rewrite/score_text/similarity. Other survivors
(66/71/72/113/118/209 constants + boundaries) are annotated in survivors.md.
"""

from __future__ import annotations

from eval import baselines as B


class TestFullLoopAcceptance:
    """Survivor baselines.py:190 — `cand_sim >= sim_bar and cand_score <= best`.

    With `or`, a candidate that fails the similarity gate but lowers the score
    is accepted, breaking the quality guarantee."""

    def test_low_similarity_candidate_rejected(self, monkeypatch) -> None:
        seen = {"rewrite_calls": 0}

        def _rewrite(text, strength=0.5, **_kw):
            seen["rewrite_calls"] += 1
            return f"rewritten-{seen['rewrite_calls']}"

        def _score(text, tier="lite", threshold=0.3):
            # source is flagged (0.5); candidates score 0.2 (not flagged)
            flagged = text == "source text"
            return {"max": 0.5 if flagged else 0.2,
                    "mean": 0.5 if flagged else 0.2,
                    "flagged": flagged}

        def _sim(text, cand):
            # first candidate LOW similarity (rejected), second HIGH (accepted)
            return 0.5 if "rewritten-1" in cand else 0.9

        monkeypatch.setattr(B, "rewrite", _rewrite)
        monkeypatch.setattr(B, "score_text", _score)
        monkeypatch.setattr(B, "similarity", _sim)
        monkeypatch.setattr(B, "recommended_bar", lambda: 0.6)
        out = B.full_loop("source text", tier="lite", threshold=0.3, max_iters=2)
        # the low-sim candidate must NOT win; the high-sim one must
        assert out.text == "rewritten-2", out.text


class TestAPILoopRewriterDispatch:
    """Survivor baselines.py:230 — `rw is not None` -> `rw is None`.

    With a real rewriter passed, the loop must call rw.rewrite (not the
    deterministic fallback). The mutation skips the rewriter entirely."""

    def test_rewriter_object_is_used(self, monkeypatch) -> None:
        calls = {"rw": 0, "fallback": 0}

        def _rewrite(text, strength=0.5, **_kw):
            calls["fallback"] += 1
            return "fallback-candidate"

        def _score(text, tier="lite", threshold=0.3):
            flagged = text == "source text"
            return {"max": 0.5 if flagged else 0.2,
                    "mean": 0.5 if flagged else 0.2,
                    "flagged": flagged}

        def _sim(text, cand):
            return 0.9

        monkeypatch.setattr(B, "rewrite", _rewrite)
        monkeypatch.setattr(B, "score_text", _score)
        monkeypatch.setattr(B, "similarity", _sim)
        monkeypatch.setattr(B, "recommended_bar", lambda: 0.6)

        class _FakeRW:
            def rewrite(self, text, score, threshold):
                calls["rw"] += 1
                return "rw-candidate"

        monkeypatch.setattr("untell.rewriter.get_rewriter", lambda *a, **k: _FakeRW())
        out = B.api_loop("source text", tier="lite", threshold=0.3, max_iters=2)
        assert calls["rw"] > 0, "the resolved rewriter must be used"
        assert out.text == "rw-candidate"
