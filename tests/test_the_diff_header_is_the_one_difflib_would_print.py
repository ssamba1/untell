"""A docstring promising equivalence to a stdlib function, and nothing checking it.

From round ninety-four's survivor list, in `untell/rich_output.py`:

    line 104  length = stop - start   ->  +    the unified-diff range column
    line 159  removed += i2 - i1      ->  +    the hunk's removed-line count
    line 425  tells_after - tells_before  ->  +  the tells delta shown to the user

`_unified_range` exists to reproduce `difflib._format_range_unified` exactly — its docstring says so:
*"Replicating that keeps the header a human sees here identical to what `difflib.unified_diff` would
print."* **Nothing compared the two.** A promise of equivalence to a stdlib function is the easiest
claim in this repository to check and it had never been checked, which is why swapping the
subtraction for an addition left the suite green.

So these tests do not assert hand-written expected strings. They assert the property the docstring
claims, **against difflib itself** — the private `_format_range_unified` where it exists, and the
public `unified_diff`'s own header where it does not. A hand-written expectation would have been
written by reading the same code it was meant to check.

⚠️ The key is `removed_lines`, not `removed`. Written as `removed` first, which is the trap
`docs/result-shapes.md` exists for — "guessing wrong returns a plausible value rather than raising",
and here it raised only because the key was absent entirely rather than merely wrong.

The third survivor is a different kind: `tells_delta` is the number a user reads to decide whether a
rewrite helped. Under `+` it reports the sum of the two counts, which is always positive and always
wrong, on a line whose surrounding comment explains that this module renders rather than measures.
"""

from __future__ import annotations

import difflib

import pytest

from untell.rich_output import _unified_range, humanize_diff


@pytest.mark.parametrize("start,stop", [
    (0, 0), (0, 1), (0, 2), (0, 10), (3, 4), (3, 3), (5, 9), (12, 40), (100, 101),
])
def test_the_range_column_is_exactly_what_difflib_formats(start: int, stop: int):
    """The docstring's promise, checked against the function it names rather than against a guess."""
    assert _unified_range(start, stop) == difflib._format_range_unified(start, stop)


def test_an_empty_range_and_a_single_line_are_the_two_special_cases():
    """Named separately because they are the branches, and both are difflib's own conventions."""
    assert _unified_range(4, 4) == difflib._format_range_unified(4, 4)
    assert _unified_range(4, 5) == difflib._format_range_unified(4, 5)
    assert "," not in _unified_range(4, 5), "a single-line range is just the line number"
    assert _unified_range(4, 4).endswith(",0"), "an empty range ends in ,0"


def test_the_header_matches_what_unified_diff_itself_emits():
    """End to end: the header a human sees, against the stdlib's own rendering of the same edit."""
    original = "alpha\nbeta\ngamma\ndelta\n"
    final = "alpha\nBETA\ngamma\ndelta\n"
    ours = humanize_diff(original, final)
    theirs = [
        line for line in difflib.unified_diff(
            original.splitlines(), final.splitlines(), lineterm="", n=0)
        if line.startswith("@@")
    ]
    assert theirs, "premise: difflib emits a hunk header for this edit"
    for hunk in ours["hunks"]:
        column = _unified_range(hunk["start_original"],
                                hunk["start_original"] + hunk["count_original"])
        assert any(f"-{column}" in header for header in theirs), (theirs, column)


def test_the_removed_count_is_the_number_of_lines_actually_removed():
    """Kills `i2 - i1` -> `+` at line 159, which no header-only assertion reaches."""
    original = "one\ntwo\nthree\nfour\nfive\n"
    final = "one\nfive\n"
    diff = humanize_diff(original, final)
    assert diff["removed_lines"] == 3, diff
    assert sum(h["count_original"] for h in diff["hunks"]) == 3


def test_counts_are_zero_when_nothing_changed():
    diff = humanize_diff("alpha\nbeta\n", "alpha\nbeta\n")
    assert diff["removed_lines"] == 0
    assert diff["added_lines"] == 0
    assert diff["hunks"] == []
    assert diff["changed"] is False


def test_the_counts_scale_with_the_size_of_the_edit():
    """A single fixed case passes under several wrong arithmetics; a family does not."""
    for extra in (1, 2, 5):
        original = "keep\n" + "drop\n" * extra + "keep\n"
        diff = humanize_diff(original, "keep\nkeep\n")
        assert diff["removed_lines"] == extra, extra
