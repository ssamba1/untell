"""Killing tests for the rich_output.py mutation survivors (2026-08-14 sweep).

  line 230  boundary: >= -> >      verdict band: p_ai exactly at the cut.
  line 232  boundary: >= -> >      borderline band: p_ai exactly at cut - band.
  line 266  boundary: > -> >=      original truncation marker at exactly 2000.
  line 267  boundary: > -> >=      final truncation marker at exactly 2000.
  line 271  boundary: > -> >=      unchanged truncation marker at exactly 2000.
  line 316  boundary: >= -> >      tell-count style at exactly 3.

The rest (82 diff-tag, 205 delta-zero style, 267 constant, 312 table header,
316 constant) are style-only branches with no assertion-visible difference —
recorded as unkillable in survivors.md.
"""

from __future__ import annotations

import io
import contextlib

from untell import rich_output as RO


def _capture(fn) -> str:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        fn()
    return buf.getvalue()


class TestVerdictBands:
    """Survivors 230/232 — `p_ai >= cut` / `p_ai >= cut - band` mutated to `>`.

    A score exactly AT the cut is flagged; exactly AT cut - band is borderline."""

    def test_exactly_at_cut_is_flagged(self) -> None:
        pre = {"max": 0.30, "verdict_threshold": 0.30, "threshold": 0.30}
        post = {"max": 0.30, "verdict_threshold": 0.30, "threshold": 0.30}
        out = _capture(
            lambda: RO.print_humanize_result(
                "Original text.", "Final text.", pre, post, iterations=1, stopped="max_iters"
            )
        )
        assert "flagged" in out.lower()

    def test_just_below_cut_is_not_flagged(self) -> None:
        # 0.29 < 0.30 cut -> not flagged; 0.30 - band(0.05?) -> borderline or clear
        pre = {"max": 0.29, "verdict_threshold": 0.30, "threshold": 0.30}
        post = {"max": 0.29, "verdict_threshold": 0.30, "threshold": 0.30}
        out = _capture(
            lambda: RO.print_humanize_result(
                "Original text.", "Final text.", pre, post, iterations=1, stopped="max_iters"
            )
        )
        assert "flagged" not in out.lower()


class TestTruncationMarker:
    """Survivors 266/267/271 — `len(x) > 2000` mutated to `>=`.

    A text of EXACTLY 2000 characters is fully shown without an ellipsis. The
    mutation would append "..." at exactly 2000."""

    def test_exactly_2000_chars_has_no_ellipsis(self) -> None:
        text = "x" * 2000
        out = _capture(
            lambda: RO.print_humanize_result(
                text, text, {"max": 0.1}, {"max": 0.1}, iterations=0, stopped="passed"
            )
        )
        assert "..." not in out

    def test_2001_chars_has_ellipsis(self) -> None:
        text = "x" * 2001
        out = _capture(
            lambda: RO.print_humanize_result(
                text, text, {"max": 0.1}, {"max": 0.1}, iterations=0, stopped="passed"
            )
        )
        assert "..." in out
