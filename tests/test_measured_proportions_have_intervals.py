"""Every proportion in the measurement log must carry a stated interval.

`docs/free-ceiling-measured.md` reports counts — "5 of 30 flagged", "4/10". A count is a point
estimate, and at these sample sizes the uncertainty routinely exceeds the effect under discussion.
The document carries one table of every distinct proportion with its Wilson interval; this test
fails if a proportion appears in the prose without a row, so adding a result cannot silently
reintroduce a bare estimate.
"""

from __future__ import annotations

import re
from pathlib import Path

from eval.pre_llm_fpr import wilson_interval

DOC = Path(__file__).resolve().parent.parent / "docs" / "free-ceiling-measured.md"
BODY = DOC.read_text(encoding="utf-8")
PROPORTION = re.compile(r"\b(\d{1,4})\s*(?:/|\s+of\s+)\s*(\d{1,4})\b")
ROW = re.compile(r"^\|\s*(\d+)/(\d+)\s*\|", re.M)


def _proportions(text: str) -> set[tuple[int, int]]:
    found = set()
    for match in PROPORTION.finditer(text):
        k, n = int(match.group(1)), int(match.group(2))
        if 0 < n <= 1000 and k <= n:
            found.add((k, n))
    return found


TABLE_ROWS = {(int(k), int(n)) for k, n in ROW.findall(BODY)}


def test_the_interval_table_exists_and_is_populated():
    """Guards the guard: a parsing change returning an empty set would make the check vacuous."""
    assert len(TABLE_ROWS) >= 100, f"parsed only {len(TABLE_ROWS)} table rows"


def test_every_proportion_in_the_prose_has_an_interval():
    missing = _proportions(BODY) - TABLE_ROWS
    assert not missing, (
        f"{len(missing)} proportion(s) reported without an interval: {sorted(missing)[:10]}. "
        f"Add rows with eval.pre_llm_fpr.wilson_interval(k, n)."
    )


def test_the_table_states_that_a_zero_count_is_not_a_zero_rate():
    """`0 of 8` reads as 'never happens' unless the document says otherwise, and its interval runs
    past 30%. That sentence is the point of the table, so it is pinned."""
    assert "not \"zero percent\"" in BODY or 'not "zero percent"' in BODY


def test_a_sampled_row_matches_the_arithmetic():
    """The table is generated; this checks it was generated with the function it claims."""
    match = re.search(r"^\|\s*5/30\s*\|\s*([\d.]+)%\s*\|\s*([\d.]+)% – ([\d.]+)%\s*\|", BODY, re.M)
    assert match, "the 5/30 row this repo quotes most is missing"
    low, high = wilson_interval(5, 30)
    assert abs(float(match.group(2)) - low * 100) < 0.15
    assert abs(float(match.group(3)) - high * 100) < 0.15
