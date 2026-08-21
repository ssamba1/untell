"""Regression guard: _FRONTABLE_RE must NOT exhibit O(n^2) backtracking.

Root cause (now fixed):
    The pattern `.{20,}?[,]?\\s+<sub>` was O(n^2) because `.` matches spaces.
    For each of n lengths of `.{20,}?`, the engine tried O(n) lengths for the
    adjacent `\\s+` — measured: n=5000 took 4.5 s, n=20000 took 154 s.

Fix (structural.py): `.{20,}?` → `.{19,}?\S`
    `\S` forces `main` to end at a non-space character.  The total number of
    `\s+` tries across all anchors equals the sum of all space-run lengths in the
    string, which is ≤ n, so the match is O(n) in string length.

Adversarial input: 20 non-space chars + k spaces + 1 non-space char + nothing
    that the pattern can use as `sub`.  Forces the engine to explore all k lengths
    of `\s+` exactly once (at the first anchor), then skip the remaining O(k)
    positions where `\S` fails on spaces, then reject at the final anchor.
    Total: O(n).  Any O(n^2) regression makes this test time out in < 2 s.
"""

from __future__ import annotations

import threading
import time

import pytest

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("UNTELL_LITE_NO_TORCH", "1")

from untell.rewriter.structural import _FRONTABLE_RE  # type-ignore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _timed_match(text: str, timeout_s: float = 2.0) -> float:
    """Return elapsed seconds, or raise AssertionError on timeout."""
    result: list[float | None] = [None]

    def _run() -> None:
        t0 = time.monotonic()
        _FRONTABLE_RE.match(text)
        result[0] = time.monotonic() - t0

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    thread.join(timeout=timeout_s)
    if thread.is_alive():
        raise AssertionError(
            f"_FRONTABLE_RE timed out after {timeout_s}s on input of length {len(text)}. "
            "This is the O(n^2) ReDoS signature — the fix has been reverted or bypassed."
        )
    assert result[0] is not None
    return result[0]


# ---------------------------------------------------------------------------
# Speed guard (the core regression)
# ---------------------------------------------------------------------------

class TestFrontableReIsLinear:
    """_FRONTABLE_RE must complete in O(n) time on adversarial no-match inputs."""

    # The fix is O(n).  Even at n=50000 with Python's re engine overhead,
    # empirical measurements showed < 100ms.  We allow 2 s to absorb any
    # environment slowness without letting a true O(n^2) regression slip by:
    # at n=50000, an O(n^2) regression would take >> 100 s.
    TIMEOUT_S = 2.0

    @pytest.mark.parametrize("n", [10_000, 30_000, 50_000])
    def test_no_match_completes_fast(self, n: int) -> None:
        """Long input with no subordinator must not hang."""
        # 20 a's + (n - 21) spaces + 1 a — no subordinating conjunction present.
        spaces = max(0, n - 21)
        text = "a" * 20 + " " * spaces + "a"
        elapsed = _timed_match(text, timeout_s=self.TIMEOUT_S)
        assert elapsed < self.TIMEOUT_S, (
            f"Match took {elapsed:.2f}s for n={n} — suspected O(n^2) regression"
        )

    def test_word_interleaved_no_match_completes_fast(self) -> None:
        """Realistic-looking long input with no subordinator must not hang."""
        # Words separated by single spaces — no subordinators anywhere.
        words = "foo bar baz qux quux corge grault garply "
        text = (words * 600)[:20_000]
        elapsed = _timed_match(text, timeout_s=self.TIMEOUT_S)
        assert elapsed < self.TIMEOUT_S, (
            f"Match took {elapsed:.2f}s — suspected O(n^2) regression"
        )


# ---------------------------------------------------------------------------
# Correctness guard (fix must not introduce a regression)
# ---------------------------------------------------------------------------

class TestFrontableReCorrectness:
    """_FRONTABLE_RE must still match (and not match) the right sentences."""

    SHOULD_MATCH = [
        # exact 20-char main clause
        "a" * 20 + " because " + "b" * 15,
        # 30-char main clause
        "a" * 30 + " because " + "b" * 15,
        # realistic sentences (main clause must be ≥ 20 chars)
        "They studied the material when the exam approached.",
        "The company expanded its operations after the merger was approved.",
        "She kept going forward even though the conditions were quite difficult.",
        "We stayed inside all afternoon because the weather turned unexpectedly harsh.",
    ]

    SHOULD_NOT_MATCH = [
        # main clause too short (< 20 chars)
        "Short because dependent clause here here.",
        # no subordinating conjunction
        "a" * 20 + " xyz " + "b" * 15,
        # dependent clause too short (< 12 chars)
        "a" * 20 + " because " + "b" * 5,
    ]

    @pytest.mark.parametrize("sentence", SHOULD_MATCH)
    def test_should_match(self, sentence: str) -> None:
        assert _FRONTABLE_RE.match(sentence.strip()) is not None, (
            f"Expected match but got None: {sentence!r}"
        )

    @pytest.mark.parametrize("sentence", SHOULD_NOT_MATCH)
    def test_should_not_match(self, sentence: str) -> None:
        assert _FRONTABLE_RE.match(sentence.strip()) is None, (
            f"Expected no match but got a match: {sentence!r}"
        )
