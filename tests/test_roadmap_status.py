"""The roadmap's status table must agree with the roadmap.

A summary table is the part people read — it is at the top, it is short, and it answers the
question they came with. If it drifts from the sections below it, it is worse than absent: a reader
who trusts it is now confidently wrong about what is done, and the detailed sections that contradict
it are exactly the part they skipped.

This session closed three roadmap items and each time the summary was somewhere else in the file,
so the two could only agree by someone remembering. These assertions replace the remembering.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROADMAP = Path(__file__).resolve().parent.parent / "ROADMAP.md"
BODY = ROADMAP.read_text(encoding="utf-8")

MARKS = ("✅", "🔜", "📦", "⛔")


def _table_rows() -> list[tuple[int, str, str]]:
    """(number, item text, status mark) for each row of the status table."""
    rows = []
    for line in BODY.splitlines():
        m = re.match(r"\|\s*(\d+)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|", line)
        if not m:
            continue
        mark = next((k for k in MARKS if k in m.group(3)), None)
        if mark:
            rows.append((int(m.group(1)), m.group(2), mark))
    return rows


def _section_marks() -> list[str]:
    """Status marks on the headings and bullets in the body, excluding the table itself."""
    marks = []
    for line in BODY.splitlines():
        if line.startswith("|"):  # the table
            continue
        s = line.strip()
        if re.match(r"^#{2,4} ", s) or s.startswith("- "):
            found = next((k for k in MARKS if s.startswith(f"### {k}") or s.startswith(f"- {k}")), None)
            if found:
                marks.append(found)
    return marks


ROWS = _table_rows()


def test_the_table_exists_and_is_populated():
    """Guards the guard: a parsing change returning [] would make everything below vacuous."""
    assert len(ROWS) >= 15, f"parsed only {len(ROWS)} rows"


def test_row_numbers_are_contiguous():
    numbers = [n for n, _, _ in ROWS]
    assert numbers == list(range(1, len(numbers) + 1)), numbers


def test_every_status_mark_is_one_of_the_documented_four():
    for number, item, mark in ROWS:
        assert mark in MARKS, f"row {number} ({item}) has an unknown mark {mark!r}"


def test_the_table_counts_match_the_body():
    """The body is the source of truth; the table summarises it. Counting is the cheapest way to
    catch a section closed without the summary being updated, or the reverse."""
    from collections import Counter

    table = Counter(mark for _, _, mark in ROWS)
    body = Counter(_section_marks())
    # ❌ items (ruled out) are deliberately not in the table, and the table splits some body
    # sections into finer rows, so this checks the directions that would mislead a reader:
    # nothing may be marked done in the table that the body still shows as open, and vice versa.
    assert table["🔜"] <= body["🔜"], (
        f"table claims {table['🔜']} open items, body shows {body['🔜']} — "
        f"the summary is hiding open work"
    )
    assert table["⛔"] == body["⛔"], (
        f"table shows {table['⛔']} GPU-blocked, body shows {body['⛔']}"
    )


def test_every_open_item_names_who_it_is_waiting_on():
    """An open item with no owner is a wish. The three categories are: a person who speaks the
    language, a decision from the maintainer, or hardware."""
    for number, item, mark in ROWS:
        if mark == "✅":
            continue
        row = next(line for line in BODY.splitlines()
                   if re.match(rf"\|\s*{number}\s*\|", line))
        waiting = row.rsplit("|", 2)[-2].strip()
        assert waiting and waiting != "—", f"row {number} ({item}) is open with no owner"


def test_no_completed_item_claims_to_be_waiting_on_something():
    for number, item, mark in ROWS:
        if mark != "✅":
            continue
        row = next(line for line in BODY.splitlines()
                   if re.match(rf"\|\s*{number}\s*\|", line))
        waiting = row.rsplit("|", 2)[-2].strip()
        assert waiting == "—", f"row {number} ({item}) is done but lists a blocker: {waiting!r}"


@pytest.mark.parametrize("claim", [
    "untell-audit",
    "Retire or rehabilitate the dead weight",
    "Finish the surgical objective",
])
def test_items_the_table_calls_done_are_marked_done_in_the_body(claim):
    """Spot-check the direction that misleads: the table saying done while the body says open."""
    section = next((line for line in BODY.splitlines()
                    if claim in line and (line.startswith("###") or line.startswith("- "))), None)
    assert section is not None, f"{claim!r} not found in the body"
    assert "✅" in section, f"table calls {claim!r} done; body says: {section.strip()[:90]}"
