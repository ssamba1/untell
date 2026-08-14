"""Killing tests for the code survivors of the first tells.py mutation sweep.

Survivor disposition (run 2026-08-14, 12 mutations, full tells test corpus):

  tells.py:708  boundary < -> <=   KILLED here (exactly-60-words is scored).
  tells.py:921  constant 2 -> 3    KILLED by existing tests/test_tells.py
                                    (test_formatting_category_fires_on_its_positive,
                                    diff_anchored floor 2).
  tells.py:945  constant 4 -> 5    KILLED here (CV reported at 4dp).
  tells.py:1187 boundary > -> >=   UNKILLABLE by construction: the de-dup test is
                                    `start < c_end and end > c_start`; the mutation
                                    would drop a span that ENDS exactly where a
                                    claimed one STARTS. A systematic search over every
                                    pattern pair and separator (space, empty, em-dash,
                                    period) found ZERO abutting spans — every tell
                                    pattern is word-boundary-based, and the spans of
                                    adjacent tells are always separated by whitespace
                                    or punctuation. The branch cannot fire.
  7 others (lines 1017-1083)       DOCSTRING PROSE, not code — the mutator rewrote
                                    sentences inside triple-quoted strings. Nothing to
                                    pin; recorded as noise in survivors.md.
"""

from __future__ import annotations

from untell.scripts.tells import score_tells


def _repetitive(n_filler: int, repeats: int) -> str:
    """`n_filler` unique words plus `repeats` copies of one trigram, nothing else.

    The trigram appears `repeats` times, contributing `repeats - 1` repeat-grams,
    so 4 copies give 3 repeats — exactly 5% of a 60-word text, the bar for
    repeated_phrasing to fire at all."""
    filler = [f"w{i}" for i in range(n_filler)]
    return " ".join(filler + ["alpha beta gamma"] * repeats)


class TestRepetitionWordBoundary:
    """Survivor tells.py:708 — `len(words) < 60` mutated to `<= 60`.

    The guard abstains BELOW 60 words. A 60-word text must still be scored: 60 < 60
    is False, so the repetition branch runs. The mutation would abstain at exactly
    60, which is the boundary this pins."""

    def test_exactly_60_words_is_scored(self) -> None:
        text = _repetitive(48, 4)  # 48 + 12 = 60 tokens, 3 repeat-grams (5% bar)
        assert len(text.split()) == 60
        cats = score_tells(text)["by_category"]
        assert cats.get("repeated_phrasing", 0) >= 3

    def test_59_words_abstains(self) -> None:
        text = _repetitive(47, 4)  # 47 + 12 = 59 tokens
        assert len(text.split()) == 59
        cats = score_tells(text)["by_category"]
        assert "repeated_phrasing" not in cats


class TestBurstinessPrecision:
    """Survivor tells.py:945 — `round(x, 4)` mutated to `round(x, 5)`.

    The coefficient of variation is reported at four decimals. A sentence pair whose
    CV is 0.81818... pins the 4th decimal: the mutation would report the 5-decimal
    form and the equality fails."""

    def test_cv_is_reported_at_four_decimals(self) -> None:
        # Sentences of 1 and 10 words: lengths [1, 10], mean 5.5, var 20.25,
        # std 4.5, CV 0.818181... -> round(..., 4) is 0.8182, round(..., 5) is
        # 0.81818. Exact float equality distinguishes them: an `abs=1e-4` approx
        # absorbs the difference (max |round4 - round5| is 5e-5), so this must be
        # exact — the mutation would report a different float.
        text = "One. " + "word " * 9 + "end."
        cv = score_tells(text).get("burstiness_cv")
        assert cv is not None
        assert cv == 0.8182
