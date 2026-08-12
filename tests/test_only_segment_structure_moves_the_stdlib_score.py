"""Seven formatting-only transforms move this score by exactly nothing. One moves it by 0.27.

The previous commit attributed a 0.27 drop to markdown scaffolding. That was the transform tested,
not the mechanism. Separating them over the same 8 HC3 documents:

    flat                          0.5804   8/8 flagged
    scaffolding + blank lines     0.3039   4/8
    scaffolding, no blank lines   0.3039   4/8      <- identical, so blank lines are not it
    blank lines only              0.3128   2/8      <- and scaffolding is not it either

Either alone produces nearly the whole drop and they do not compound. What they share is SHORT
SEGMENTS — a heading, a list item and a one-sentence paragraph are all short — and half of this
path's score is burstiness, the variation in sentence length, so adding short segments widens the
spread and reads as more human.

The negative result is the more useful half. Hard wrapping at 60 columns, double spaces after full
stops, leading indentation, tab indentation, CRLF endings, trailing spaces, and collapsing to one
long line each moved the mean by EXACTLY 0.0000 across all 8 documents. Whitespace normalisation
absorbs them; segment structure is the one axis left.

These tests pin both halves: the invariances, which are a real guarantee worth keeping, and the
one sensitivity, which is a known limitation of the stdlib path and is documented rather than
silently fixed — see the note beside `_STDLIB_PERPLEXITY_VERDICT_THRESHOLD`.
"""
from __future__ import annotations

import pytest

from untell.scripts.score import score_text

PROSE = (
    "Moreover, the framework leverages robust methodologies to deliver outcomes at scale. It "
    "significantly improves overall efficiency and accuracy across the evaluated corpus. "
    "Furthermore, organizations increasingly adopt these transformative technologies to optimize "
    "operational workflows across numerous sectors. In conclusion, these findings underscore the "
    "importance of a comprehensive approach here."
)


def _hard_wrap(text: str, width: int = 60) -> str:
    out, line = [], ""
    for word in text.split():
        if len(line) + len(word) + 1 > width:
            out.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    out.append(line)
    return "\n".join(out)


NEUTRAL = {
    "hard-wrap": lambda t: _hard_wrap(t),
    "double-spaces": lambda t: t.replace(". ", ".  "),
    "leading-indent": lambda t: "\n".join("    " + ln for ln in t.splitlines()),
    "tab-indent": lambda t: "\n".join("\t" + ln for ln in _hard_wrap(t).splitlines()),
    "crlf": lambda t: _hard_wrap(t).replace("\n", "\r\n"),
    "trailing-spaces": lambda t: "\n".join(ln + "   " for ln in _hard_wrap(t).splitlines()),
    "one-long-line": lambda t: " ".join(t.split()),
}


@pytest.fixture(autouse=True)
def _stdlib(monkeypatch):
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")


def test_the_baseline_is_flagged():
    """The premise. An unflagged baseline would make every comparison below vacuous."""
    assert score_text(PROSE, tier="lite")["max"] >= 0.30


@pytest.mark.parametrize("name", sorted(NEUTRAL))
def test_whitespace_only_changes_do_not_move_the_score(name: str):
    """The guarantee half: identical words in different whitespace must score identically."""
    base = score_text(PROSE, tier="lite")["max"]
    moved = score_text(NEUTRAL[name](PROSE), tier="lite")["max"]

    assert moved == pytest.approx(base, abs=0.01), (
        f"{name} changed the score {base:.4f} -> {moved:.4f} without changing a word"
    )


def test_splitting_into_one_sentence_paragraphs_does_move_it():
    """The sensitivity half — asserted as MOVEMENT, not as a direction.

    The direction belongs to the document, not the transform. On 12 HC3 documents splitting moved
    the score down 12 times out of 12 (mean -0.2616, largest -0.3912), and this fixture — five
    long, uniform sentences — moves the other way, 0.5331 -> 0.6627. Splitting raises the spread
    when the sentences were uniform and lowers it when they were already varied, so the first
    version of this test asserted the corpus direction against a fixture that does the opposite,
    and failed.

    Pinned as it currently behaves rather than as it should. Fixing it means scoring
    `layout.blocks()` rather than the raw document, which moves every stdlib figure in the
    repository; a test encoding the desired behaviour would make that measurement pass harder.
    """
    base = score_text(PROSE, tier="lite")["max"]
    split = "\n\n".join(s.strip() for s in PROSE.split(". ") if s.strip())
    moved = score_text(split, tier="lite")["max"]

    assert abs(moved - base) > 0.05, (
        f"re-segmenting no longer moves the score ({base:.4f} -> {moved:.4f}); if that is a "
        "deliberate fix, the note beside _STDLIB_PERPLEXITY_VERDICT_THRESHOLD needs updating"
    )
