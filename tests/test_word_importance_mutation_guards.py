"""Killing tests for word_importance.py mutation survivors (2026-08-14 sweep).

  line 841  boundary: >= -> >      max_subs cap in the greedy loop.
  line 843  boundary: <= -> <      zero-drop word filter.

Killed here via controlled monkeypatches. The other survivors (435 WordNet-gated,
547/580/651 constants, 739 default, 876 x3 acceptance criteria) are annotated.
"""

from __future__ import annotations

import pytest

from untell.attacks import word_importance as W


class TestMaxSubsCap:
    """Survivor word_importance.py:841 — `subs >= max_subs` mutated to `>`.

    With max_subs=1, exactly ONE substitution is applied. The mutation allows a
    second — the reported `substitutions` count differs."""

    def test_cap_honored_at_exact_max(self, monkeypatch) -> None:
        text = "alpha beta gamma"
        drops = [("alpha", 0.5), ("beta", 0.5), ("gamma", 0.5)]

        def _imp(*a, **k):
            return list(drops)

        # stateful: first round scores 0.9 (accepted), second round 0.8 (also
        # accepted) — so a 2nd substitution WOULD happen if the cap allowed it
        state = {"n": 0}

        def _batch(texts, *a, **k):
            state["n"] += 1
            v = 0.9 if state["n"] == 1 else 0.8
            return [{"max": v}] * len(texts)

        monkeypatch.setattr(W, "importance", _imp)
        monkeypatch.setattr(W, "batch_score_texts", _batch)
        monkeypatch.setattr(W, "_score_max", lambda *a, **k: 0.95)
        monkeypatch.setattr(W, "synonyms", lambda w: ["syn_a", "syn_b"])
        monkeypatch.setattr(W, "substitute_once", lambda cur, word, syn: cur.replace(word, syn, 1))
        result = W.surgical_substitute(text, tier="lite", max_subs=1)
        # max_subs=1 caps at exactly one substitution even though the 2nd word
        # would also be accepted (0.8 < 0.9)
        assert result["substitutions"] == 1


class TestZeroDropFilter:
    """Survivor word_importance.py:843 — `drop <= 0` mutated to `<`.

    A word with drop EXACTLY 0 must be skipped (it cannot lower the score). The
    mutation processes it, consuming a substitution slot."""

    def test_zero_drop_word_skipped(self, monkeypatch) -> None:
        text = "alpha beta"
        drops = [("alpha", 0.0), ("beta", 0.5)]

        def _imp(*a, **k):
            return list(drops)

        def _batch(texts, *a, **k):
            return [{"max": 0.5}] * len(texts)

        monkeypatch.setattr(W, "importance", _imp)
        monkeypatch.setattr(W, "batch_score_texts", _batch)
        monkeypatch.setattr(W, "_score_max", lambda *a, **k: 0.6)
        monkeypatch.setattr(W, "synonyms", lambda w: ["syn_a"])
        monkeypatch.setattr(W, "substitute_once", lambda cur, word, syn: cur.replace(word, syn, 1))
        result = W.surgical_substitute(text, tier="lite", max_subs=8)
        # alpha (drop 0) skipped: only beta substituted -> 1 substitution
        assert result["substitutions"] == 1
        assert "beta" not in result["text"]
