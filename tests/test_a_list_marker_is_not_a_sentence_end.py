"""`restore(lock(text))` rewrote a document in which nothing had been rewritten.

`restore` capitalises a locked span that lands at a sentence start. That pass exists for a real
defect: a span locked mid-sentence carries mid-sentence casing, and when the loop splits the
sentence in front of it the restored text reads "...in the book industry. the New York Times Best
seller list is...".

It decided "sentence start" by looking for `[.!?]` before the sentinel, and the "." of an ordered
list marker matched. MEASURED on this repo's own docs, with no rewriter involved at all:

    docs/free-ceiling-report.md, 10,250 characters, differing by exactly one
      "1. untell's actual inference-only % flagged ..."
      -> "1. Untell's actual inference-only % flagged ..."

`lock` then `restore` with nothing in between must be the identity; here it was a text edit, which
is the one thing the preserve layer promises never to do. And it is the product's own deliberately
lowercase name. A round trip was the invariant being violated, so no coverage test could have found
it — it needed the round trip run over real prose.

A list item's first word is already where its author put it. The capitalisation pass is for spans
the loop MOVED, so a marker is excluded and everything else is untouched.

The targeted tests drive `restore` with a hand-built mapping rather than through `lock`. The span
that triggered this in the wild — a bare lowercase product name — is locked by the entity pass,
which needs surrounding context and an optional dependency, so a synthetic sentence fed to `lock`
locks nothing and the test would pass while exercising none of the code. `restore`'s contract is
what changed and `restore` is what these call.
"""

from __future__ import annotations

import glob
import io

import pytest

from untell.scripts.preserve import lock, restore

SENTINEL = "⟦HZ0000⟧"

# (label, masked text, what the span restores to, expected output)
KEEPS_CASE = [
    ("numbered dot", f"1. {SENTINEL}'s rate is the open question.", "untell",
     "1. untell's rate is the open question."),
    ("numbered paren", f"1) {SENTINEL}'s rate is the open question.", "untell",
     "1) untell's rate is the open question."),
    ("double digit", f"12. {SENTINEL}'s rate is the open question.", "untell",
     "12. untell's rate is the open question."),
    ("indented", f"  3. {SENTINEL} is the open question.", "untell",
     "  3. untell is the open question."),
    ("mid document", f"Prior work is cited.\n\n2. {SENTINEL} is the open question.", "untell",
     "Prior work is cited.\n\n2. untell is the open question."),
]


@pytest.mark.parametrize(
    "name,masked,span,expected", KEEPS_CASE, ids=[c[0] for c in KEEPS_CASE]
)
def test_a_list_item_keeps_its_authors_casing(
    name: str, masked: str, span: str, expected: str
) -> None:
    assert restore(masked, {SENTINEL: span}) == expected, name


def test_a_moved_span_at_a_real_sentence_start_is_still_capitalised():
    """The behaviour the pass exists for, which the fix must not undo."""
    masked = f"Sales rose in the book industry. {SENTINEL} list is cited widely."
    assert restore(masked, {SENTINEL: "the new york times"}) == (
        "Sales rose in the book industry. The new york times list is cited widely."
    )


def test_a_span_at_the_very_start_is_still_capitalised():
    assert restore(f"{SENTINEL} is cited widely.", {SENTINEL: "the new york times"}) == (
        "The new york times is cited widely."
    )


def test_a_sentence_ending_in_a_number_still_capitalises_what_follows():
    """The narrow reading matters: the exclusion is for a marker that OPENS a line, not for any
    "." with a digit before it. A sentence ending in a year must not lose the pass."""
    masked = f"The trial ran through 2024. {SENTINEL} list is cited widely."
    assert restore(masked, {SENTINEL: "the new york times"}) == (
        "The trial ran through 2024. The new york times list is cited widely."
    )


def test_every_document_in_the_repo_survives_a_round_trip():
    """The check that found this — `restore(lock(t)) == t` over real prose rather than fixtures."""
    failures = []
    for path in sorted(glob.glob("docs/*.md")) + sorted(glob.glob("*.md")):
        try:
            text = io.open(path, encoding="utf-8").read()
        except OSError:
            continue
        masked, mapping = lock(text)
        if restore(masked, mapping) != text:
            failures.append(path)
    assert not failures, f"round trip changed these documents: {failures}"
