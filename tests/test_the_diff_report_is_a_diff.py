"""The change report compared word *i* of one text against word *i* of the other.

That is a positional zip, not a diff, and it is correct only when the rewrite preserves word count
exactly. A single insertion shifts every following word out of alignment and paints it as changed.
MEASURED on a seven-word sentence:

    one word inserted at the front   7 of 8 words marked changed
    one word inserted mid-sentence   6 of 8
    one word deleted                 5 of 6
    one word substituted             1 of 7      <- the only shape it got right

And MEASURED on 17 real `composite` rewrites of HC3 paragraphs, which insert openers, delete
transitions and split sentences on almost every run:

    words the report marked as changed
       positional zip   61.2%
       difflib           2.9%

A 21x overstatement, in the view a user reads to judge whether the tool makes minimal,
meaning-preserving edits — so the report was arguing against the thing it exists to demonstrate.
"""

from __future__ import annotations

import pytest

import untell.rich_output as rich_output

rich = pytest.importorskip("rich", reason="the diff renders plain text without rich installed")


@pytest.fixture(autouse=True)
def _rich_enabled(monkeypatch: pytest.MonkeyPatch):
    """`_diff_words` returns `b` unchanged when rich is absent, which would make every assertion
    below vacuous. Force the styled path."""
    from rich.text import Text

    monkeypatch.setattr(rich_output, "_RICH", True)
    monkeypatch.setattr(rich_output, "_Text", Text)


def _classify(before: str, after: str) -> tuple[list[str], set[str], set[str]]:
    """Marked WORDS, not marked spans.

    `difflib` emits contiguous runs, so a four-word replacement is one span rather than four — which
    is better output and fewer spans, and made the first version of two tests here fail on their own
    bookkeeping rather than on the code.
    """
    text = rich_output._diff_words(before, after)
    added: set[str] = set()
    removed: set[str] = set()
    for span in text.spans:
        words = text.plain[span.start : span.end].split()
        if span.style == "bold green":
            added.update(words)
        elif span.style == "dim strike":
            removed.update(words)
    return text.plain.split(), added, removed


SENTENCE = "the cat sat on the mat today"


@pytest.mark.parametrize(
    ("name", "after", "added", "removed"),
    [
        ("inserted at front", "a the cat sat on the mat today", {"a"}, set()),
        ("inserted mid", "the cat quickly sat on the mat today", {"quickly"}, set()),
        ("substituted", "the dog sat on the mat today", {"dog"}, set()),
        ("deleted", "the sat on the mat today", set(), {"cat"}),
        ("unchanged", SENTENCE, set(), set()),
    ],
    ids=lambda x: str(x)[:18],
)
def test_only_the_real_edit_is_marked(name: str, after: str, added: set, removed: set) -> None:
    _, got_added, got_removed = _classify(SENTENCE, after)
    assert got_added == added, name
    assert got_removed == removed, name


def test_a_deletion_shows_what_was_removed() -> None:
    """The positional version appended a bare space for a deleted word, so a dropped clause left no
    trace in the report — and "did the rewriter drop my content" is one of the questions this view
    exists to answer."""
    _, _, removed = _classify("the cat sat on the mat today", "the mat today")
    assert removed, "a deletion rendered as nothing at all"
    assert {"cat", "sat", "on"} & removed


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ("", "the cat sat"),
        ("the cat sat", ""),
        ("", ""),
        ("one\ntwo\nthree", "one\ntwo\nfour"),
        ("a b", "a b c d e f"),
        ("a b c d e f", "a b"),
    ],
    ids=lambda x: repr(x)[:16],
)
def test_the_edges_do_not_raise(before: str, after: str) -> None:
    assert rich_output._diff_words(before, after) is not None


def test_an_unrelated_rewrite_is_still_mostly_marked() -> None:
    """Guards the guard. A diff that marks nothing would pass every test above — the fix must not
    have made the report silent, only accurate."""
    _, added, _ = _classify("alpha beta gamma delta", "epsilon zeta eta theta")
    assert len(added) >= 3, added


def test_it_reports_a_small_edit_as_small() -> None:
    """The property the 61.2% -> 2.9% measurement is about, as an invariant rather than a number:
    changing one word in a long paragraph must not mark most of the paragraph."""
    words = [f"word{i}" for i in range(60)]
    before = " ".join(words)
    after = " ".join(["inserted", *words])

    _, added, removed = _classify(before, after)
    assert added | removed == {"inserted"}, sorted(added | removed)
