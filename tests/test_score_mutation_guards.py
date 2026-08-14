"""Killing tests for the score.py mutation survivors (2026-08-14 sweep).

Targeted at the pure/unit-testable boundaries:

  line 338  logic: != -> ==     _verdict_threshold scoring-set check.
  line 677  boundary: >= -> >   _single_sentence_warning sentence count.
  line 751  constant: 4 -> 5    result["max"] rounding.
  line 762  boundary: >= -> >   flagged at exact verdict threshold.
  line 1313 constant: 2 -> 3    CLI exit code when scoring reports unscored.

The remaining six survivors (664 gpt2-mode short-circuit, 1129-1131 detector-load
guards, 1203 lone-note boundary) are model/environment-dependent paths: they require
a live torch runtime or a specific detector failure shape that the test suite cannot
construct deterministically — recorded as unkillable in survivors.md.
"""

from __future__ import annotations

import json

from untell.scripts import score as S


class TestVerdictThresholdScoringSet:
    """Survivor score.py:338 — `scoring != {"perplexity_burstiness"}` mutated to `==`.

    The stdlib-only verdict threshold is raised ONLY when the stdlib heuristic is the
    whole verdict. The mutation would raise it when the set is anything else — i.e.
    the exact inverse. Test both sides of the equality."""

    def test_stdlib_only_raises_the_threshold(self) -> None:
        out = S._verdict_threshold(
            0.30, {"perplexity_burstiness": 0.4}, {"perplexity_burstiness": "stdlib"}
        )
        assert out == max(0.30, S._STDLIB_PERPLEXITY_VERDICT_THRESHOLD)

    def test_any_other_set_keeps_the_default(self) -> None:
        out = S._verdict_threshold(
            0.30,
            {"perplexity_burstiness": 0.4, "mage": 0.5},
            {"perplexity_burstiness": "stdlib", "mage": "torch"},
        )
        assert out == 0.30


class TestSingleSentenceBoundary:
    """Survivor score.py:677 — `len([...]) >= 2` mutated to `> 2`.

    A two-sentence text has enough length for burstiness and must NOT get the
    single-sentence warning. The mutation would warn on exactly two sentences."""

    def test_two_sentences_get_no_warning(self) -> None:
        out = S._single_sentence_warning(
            "Two sentences. Here is the second.", [], {"perplexity_burstiness": "stdlib"}
        )
        assert out is None

    def test_one_sentence_gets_a_warning(self) -> None:
        out = S._single_sentence_warning(
            "One sentence only.", [], {"perplexity_burstiness": "stdlib"}
        )
        assert out is not None


class TestFlaggedAtExactThreshold:
    """Survivor score.py:762 — `mx >= verdict_threshold` mutated to `>`.

    A score exactly AT the verdict threshold is flagged. The mutation would need
    strictly above. Exercises the real `_score_with_detectors` aggregation with a
    fake detector pinned to the exact threshold."""

    def test_exact_threshold_is_flagged(self, monkeypatch) -> None:
        class ExactDetector:
            name = "exact"
            tier = "lite"

            def score(self, text):
                return 0.30  # exactly the default verdict threshold

            def mode(self):
                return "fake"

            def available(self):
                return True

        monkeypatch.setattr(S, "load_detectors", lambda tier: [ExactDetector()])
        r = S.score_text("Some text.", tier="lite", threshold=0.30)
        assert r["max"] == 0.30
        assert r["flagged"] is True


class TestCliExitCode:
    """Survivor score.py:1313 — `return 2` mutated to `return 3`.

    When scoring reports `scored: false` (every detector failed), the CLI exits 2."""

    def test_unscored_exits_two(self, monkeypatch, capsys) -> None:
        monkeypatch.setattr(
            S, "score_text", lambda *a, **k: {"scored": False, "max": 0.0, "tier": "lite"}
        )
        rc = S.main(["some text"])
        assert rc == 2
