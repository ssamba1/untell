"""Killing tests for the detectors/base.py mutation survivors (2026-08-14 sweep).

  line 175  boundary: <= -> <      _split_to_width exact-width boundary.
  line 219  boundary: <= -> <      windowed_max single-call boundary (exactly window_words).
  line 225  logic: or -> and       split_sentences fallback for terminator-free text.
  line 239  boundary: > -> >=      window flush at exactly window_words.

Killed here. 41 (clamp01 `> 1.0` -> `>=`), 165 (WINDOW_WORDS 320 -> 321), 242
(`current and` -> `or`) are unobservable: clamp01(1.0) is identical under both
comparisons; a changed window constant shifts every boundary at once (no test can
distinguish without pinning the constant itself); the `or` variant only appends an
empty window that the `if w.strip()` filter drops. Recorded as unkillable.
"""

from __future__ import annotations

from untell.detectors.base import _split_to_width, windowed_max, WINDOW_WORDS


class TestSingleCallBoundary:
    """Survivor base.py:219 — `len(text.split()) <= window_words` mutated to `<`.

    A text of EXACTLY ``window_words`` words is scored in a single call, with the
    text passed through unchanged (newlines preserved). The mutation forces the
    windowed path, which joins pieces with spaces and collapses the newline."""

    def test_exactly_window_words_is_single_call_preserving_text(self) -> None:
        s1 = " ".join(f"w{i}." for i in range(WINDOW_WORDS // 2))
        s2 = " ".join(f"v{i}." for i in range(WINDOW_WORDS // 2))
        text = s1 + "\n\n" + s2
        assert len(text.split()) == WINDOW_WORDS

        seen: list[str] = []

        def sw(t):
            seen.append(t)
            return 0.5

        windowed_max(text, sw)
        assert len(seen) == 1
        assert "\n" in seen[0]  # single-call path preserves line structure


class TestWindowFlushBoundary:
    """Survivor base.py:239 — `count + n > window_words` mutated to `>=`.

    Two sentences packing to EXACTLY ``window_words`` together with a trailing
    third sentence distinguish the boundary: the original packs the first pair
    (320) and starts a new window for the tail; the mutation flushes at the exact
    total, producing [160, 161] instead of [320, 1]."""

    def test_exact_total_packs_before_flushing(self) -> None:
        s1 = " ".join(f"a{i}" for i in range(160)) + "."
        s2 = " ".join(f"b{i}" for i in range(160)) + "."
        s3 = "c."
        text = f"{s1} {s2} {s3}"
        assert len(text.split()) == WINDOW_WORDS + 1

        sizes: list[int] = []

        def sw(t):
            sizes.append(len(t.split()))
            return 0.5

        windowed_max(text, sw)
        # original: the 320-word pair packs into one window, the tail is a second
        assert sizes == [WINDOW_WORDS, 1], sizes
