"""Two results shared a number, and the number is how the rest of the repository cites them.

`docs/free-ceiling-measured.md` is the measurement record. Source comments and test docstrings point
at it by number — "Result 163 measured that improving the tier `max` stops improving a detector the
loop never sees" appears in `untell/scripts/run.py` and in a test — so a duplicate heading makes a
citation ambiguous rather than merely untidy.

FOUND by parsing the headings, which nothing had done across 226 results and 103,000 words:

    headings     226
    duplicates   163, 212     two distinct results each sharing a number with an earlier one
    gaps         7, 136, 145

The first parse of this file reported 222 headings and six gaps. Both figures were wrong, and the
test caught it: the pattern was anchored on a bare `## Result N` line, and the first 39 results are
titled (`## Result 10 — the corpus was doing more work than anything measured above`) with four more
at H3. 43 real results read as absent, and the citation check duly reported Results 10, 12, 15, 19,
32, 38 and 43 as "cited but never written" — every one of them present, one heading style away.

The duplicates survived the correction and were real.

The duplicates are suffixed (`163b`, `212b`) rather than renumbered, because the two citations of
Result 163 both mean the earlier one and reassigning the number would silently redirect them. The
gaps are left alone: a missing number is a result that was withdrawn or merged, which is a fact
about the history and not a defect in it.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import pytest

LOG = Path(__file__).resolve().parents[1] / "docs" / "free-ceiling-measured.md"
# Matches BOTH heading styles. The bare `## Result 163` form is the recent one; the first 39
# results are titled — `## Result 10 — the corpus was doing more work than anything measured
# above` — and four sit at H3. A pattern anchored on `## ... $` sees 183 of 226 and reports the
# other 43 as "cited but never written", which is what the first version of this file did.
HEADING = re.compile(r"(?m)^#+\s*Result (\d+[a-z]?)(?![0-9])")


@pytest.fixture(scope="module")
def numbers() -> list[str]:
    if not LOG.exists():
        pytest.skip("results log not present")
    found = HEADING.findall(LOG.read_text(encoding="utf-8"))
    assert found, "no result headings parsed — the heading format has changed"
    return found


def test_no_result_number_is_used_twice(numbers: list[str]) -> None:
    """The property that matters. Everything else in this file is a sanity check on the parse."""
    duplicated = sorted(n for n, count in Counter(numbers).items() if count > 1)
    assert not duplicated, duplicated


def test_the_numbers_are_in_document_order(numbers: list[str]) -> None:
    """A record read top to bottom should count upward. A result inserted above an earlier one is
    either a mis-numbering or a rewritten history, and both are worth seeing."""
    plain = [int(re.match(r"\d+", n).group(0)) for n in numbers]
    descending = [(a, b) for a, b in zip(plain, plain[1:]) if b < a]
    assert not descending, descending


def test_every_cited_result_exists(numbers: list[str]) -> None:
    """A citation pointing at a number nobody wrote is worse than a duplicate: it reads as evidence
    and there is nothing behind it. Scans the package and the suite for `Result N` references."""
    root = LOG.resolve().parents[1]
    cited: set[str] = set()
    for path in list((root / "untell").rglob("*.py")) + list((root / "tests").rglob("*.py")):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):  # pragma: no cover - environmental
            continue
        cited.update(re.findall(r"\bResult (\d+)\b", text))
    known = {re.match(r"\d+", n).group(0) for n in numbers}
    missing = sorted(cited - known, key=int)
    assert not missing, f"cited but never written: {missing}"


def test_the_log_is_still_growing(numbers: list[str]) -> None:
    """Guards the guard. Every assertion above passes on an empty file; this one fails if the parse
    silently stops matching, which is how a format change would present."""
    assert len(numbers) > 200, len(numbers)
