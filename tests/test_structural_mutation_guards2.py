"""Killing tests for structural.py mutation survivors (2026-08-14 sweep, wave 2).

  line 2623 constant: 2 -> 3       _inside_quotes quote-parity check.

Killed here. 2789 (`len(sents) >= 2` merge guard) is unkillable by construction:
with exactly 2 sentences the merge candidate collapses to a single sentence
(CV 0), which never beats the current CV — so the candidate never wins and the
guard's output is identical under both bounds. Remaining survivors
(480/755/1043/1654/1678/2298/2513/2853/2866/2875) annotated in survivors.md.
"""

from __future__ import annotations

from untell.rewriter import structural as S


class TestInsideQuotes:
    """Survivor structural.py:2623 — `count('"') % 2 == 1` mutated to `% 3 == 1`.

    An ODD number of quotes to the left means the break is inside a quotation
    (2 quotes = balanced pair, not inside). The mutation (mod 3) misreads 3 quotes
    as balanced."""

    def test_two_quotes_is_balanced(self) -> None:
        words = ['He', 'said', '"', 'the', 'result', 'is', 'robust', '"', 'and']
        # break before 'and': exactly 2 quotes to the left -> not inside
        assert S._inside_quotes(words, 8) is False

    def test_one_quote_is_inside(self) -> None:
        words = ['He', 'said', '"', 'the', 'result', 'is']
        # break before 'the' (index 3): 1 quote to the left -> inside
        assert S._inside_quotes(words, 3) is True

    def test_three_quotes_is_inside(self) -> None:
        words = ['"', 'a', '"', 'then', '"', 'b', 'c']
        # break before 'b' (index 5): 3 quotes to the left -> inside (odd)
        assert S._inside_quotes(words, 5) is True
