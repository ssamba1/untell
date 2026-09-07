"""Advisory-note thresholds in `untell/scripts/score.py` that survived the boundary sweep.

These notes qualify a score rather than produce one, which is exactly why they rot unnoticed: a
wrong bar here does not fail anything, it just tells the user something untrue about their own
text. Each case below sits ON its constant, where a `>` / `>=` swap is the only thing that shows.

Two boundaries in this file are deliberately absent, and
`test_the_locked_share_estimate_has_two_boundaries_no_test_can_reach` records why: they are
EQUIVALENT mutants, not untested ones.
"""

from __future__ import annotations

import math

from untell.scripts import score
from untell.scripts.score import (
    _LOCK_NOTE_MARGIN,
    _LOCK_NOTE_PREFIX_CHARS,
    _LOCKED_SHARE_BAR,
    _LONE_BLOCK_SHARE_BAR,
    _MIN_BLOCKS_FOR_LONE_NOTE,
    _line_per_sentence_warning,
    _mostly_locked_warning,
)


class _Shares:
    """Stateful stand-in for `_locked_share`, so a test can sit exactly on a bar.

    The real one runs spaCy NER. Patching it is not avoiding the work — the values it returns are
    the input to the comparison under test, and no real document lands on 0.500000 on demand.
    """

    def __init__(self, *values: float) -> None:
        self.values = list(values)
        self.calls: list[int] = []

    def __call__(self, text: str) -> float:
        self.calls.append(len(text))
        return self.values[min(len(self.calls) - 1, len(self.values) - 1)]


def test_text_exactly_at_the_prefix_length_is_measured_once_not_sampled_then_reread(monkeypatch):
    """`len(text) <= _LOCK_NOTE_PREFIX_CHARS` decides exact-measure vs estimate-then-maybe-reread.

    At exactly the prefix length the two paths return the SAME note — the prefix is the whole
    document — so the only observable difference is how many times the document is read. That is
    not a cosmetic difference: the module's own comment measures this call at **87.8% of
    `score_text`** on ordinary prose, 3.4s on a 50,000-character request. Under `<`, a document
    sitting exactly on the cap is locked twice and the note costs double.
    """
    shares = _Shares(_LOCKED_SHARE_BAR)  # on the bar, so the estimate path would re-read
    monkeypatch.setattr(score, "_locked_share", shares)
    _mostly_locked_warning("x" * _LOCK_NOTE_PREFIX_CHARS)
    assert shares.calls == [_LOCK_NOTE_PREFIX_CHARS], (
        "at the cap the document must be measured exactly, in one pass")


def test_one_character_over_the_prefix_length_is_estimated_and_then_reread(monkeypatch):
    """The neighbour: one character past the cap, the sampling path runs and re-reads."""
    shares = _Shares(_LOCKED_SHARE_BAR)
    monkeypatch.setattr(score, "_locked_share", shares)
    _mostly_locked_warning("x" * (_LOCK_NOTE_PREFIX_CHARS + 1))
    assert shares.calls == [_LOCK_NOTE_PREFIX_CHARS, _LOCK_NOTE_PREFIX_CHARS + 1]


def test_a_full_measure_exactly_on_the_locked_bar_is_not_mostly_locked(monkeypatch):
    """`share > _LOCKED_SHARE_BAR` on the re-read path: half-locked is not "mostly locked".

    Under `>=`, a document with exactly half its characters held is told the rewriter is forbidden
    to touch most of it, which is false at 50%.
    """
    shares = _Shares(_LOCKED_SHARE_BAR, _LOCKED_SHARE_BAR)
    monkeypatch.setattr(score, "_locked_share", shares)
    assert _mostly_locked_warning("x" * (_LOCK_NOTE_PREFIX_CHARS + 1)) is None
    assert len(shares.calls) == 2, "the re-read path is the one under test"


def test_a_hair_over_the_locked_bar_does_warn(monkeypatch):
    """The neighbour on the other side, so the bar is pinned rather than merely not-crossed."""
    over = math.nextafter(_LOCKED_SHARE_BAR, 1.0)
    shares = _Shares(_LOCKED_SHARE_BAR, over)
    monkeypatch.setattr(score, "_locked_share", shares)
    assert _mostly_locked_warning("x" * (_LOCK_NOTE_PREFIX_CHARS + 1)) is not None


def _blocks(lone: int, multi: int) -> str:
    """``lone`` one-sentence paragraphs and ``multi`` two-sentence ones."""
    return "\n\n".join(
        [f"Sentence number {i} stands alone here." for i in range(lone)]
        + [f"First half of block {i}. Second half of block {i}." for i in range(multi)])


def test_a_share_of_lone_blocks_exactly_on_the_bar_does_not_warn():
    """`lone / len(prose) > _LONE_BLOCK_SHARE_BAR`: 4 of 5 blocks is exactly 0.80.

    Under `>=` this note fires at the bar, telling the user their layout limited the rewrite when
    it is precisely at the share the constant says is acceptable.
    """
    text = _blocks(lone=4, multi=1)
    assert 4 / 5 == _LONE_BLOCK_SHARE_BAR, "the fixture must sit ON the bar"
    assert _line_per_sentence_warning(text) is None


def test_just_over_the_lone_block_share_does_warn():
    """The neighbour: 5 of 5 is over the bar and must warn, so the test is not vacuously None."""
    assert _line_per_sentence_warning(_blocks(lone=5, multi=0)) is not None


def test_the_lone_block_note_needs_a_minimum_number_of_blocks():
    """Guard on the fixture above: with too few blocks the note is skipped for a different reason,
    and a share test built on 2 blocks would pass whichever way the bar points."""
    assert _MIN_BLOCKS_FOR_LONE_NOTE <= 5


def test_the_locked_share_estimate_has_two_boundaries_no_test_can_reach():
    """Two register rows are EQUIVALENT mutants. Recording that is the honest alternative to
    writing a test that pretends to cover them.

    `_mostly_locked_warning` reads::

        if abs(estimate - _LOCKED_SHARE_BAR) > _LOCK_NOTE_MARGIN:   # line A
            return _MOSTLY_LOCKED_NOTE if estimate > _LOCKED_SHARE_BAR else None   # line B

    **Line A** flips behaviour only when `abs(estimate - 0.50) == 0.15` exactly. No IEEE double
    does: differences in `[0.5, 1)` land on a grid of 2^-53, while 0.15's representation needs the
    finer grid of `[0.125, 0.25)`, so the subtraction can never produce it.

    **Line B** is reached only when line A's guard passed, which excludes `estimate == 0.50` by
    construction — so `>` and `>=` cannot differ there either.

    Both therefore survive the sweep permanently, and no test can change that. This asserts the
    reasoning so that changing either constant re-opens the question instead of silently leaving
    two rows in the register that everyone has learned to ignore.
    """
    assert not any(
        abs(x - _LOCKED_SHARE_BAR) == _LOCK_NOTE_MARGIN
        for x in _floats_around(_LOCKED_SHARE_BAR + _LOCK_NOTE_MARGIN, 4096)
        + _floats_around(_LOCKED_SHARE_BAR - _LOCK_NOTE_MARGIN, 4096)
    ), "a float now lands exactly on the margin — line A is reachable and needs a real test"

    reachable = [e / 10_000 for e in range(10_001)
                 if abs(e / 10_000 - _LOCKED_SHARE_BAR) > _LOCK_NOTE_MARGIN]
    assert reachable, "the guard admits nothing at all, which is a different bug"
    assert not any((e > _LOCKED_SHARE_BAR) != (e >= _LOCKED_SHARE_BAR) for e in reachable), (
        "an estimate equal to the bar now reaches line B — it needs a real test")


def _floats_around(value: float, n: int) -> list[float]:
    out, up, down = [], value, value
    for _ in range(n):
        up, down = math.nextafter(up, math.inf), math.nextafter(down, -math.inf)
        out += [up, down]
    return out + [value]
