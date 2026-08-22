"""Every Unicode category that can hide a character, swept rather than guessed.

Result 213 found U+2028 and U+2029 falling between two classes: `_EXOTIC_SPACE` covers category Zs,
`score._INVISIBLE_RE` covers Cf plus the soft hyphen, and Zl/Zp are neither. That was found by
thinking of two characters. The mechanical version tests all of them.

MEASURED over every character in the BMP whose category is Zs, Zl, Zp, Cf or Cc — 95 characters —
each inserted after every "e" in a two-sentence paragraph, then scrubbed and rescored against the
baseline of 0.6735:

    Zl and Zp (2 characters)     not restored, BY DESIGN — mapped to a newline, see below
    Cf and Cc (76 characters)    restored exactly
    Zs (17 characters)           not restored, and NOT a defect — see below

**The Zs rows are a property of the probe, not the scrubber.** Inserting a real space into a word
splits it, and plain U+0020 shows the SAME figure as every exotic space -- all 17 land on one value.
No scrubber can undo that, because the damage is that the text now says something else. Normalising
an EM SPACE to a plain space is the correct handling and the score change survives it.

That shared figure was 0.0000 when this file was written and is not any more, which is the whole
reason the test below asserts the property rather than the number. The 0.0000 was an artifact of a
splitting bug: `_ends_in_a_name_prefix` treated any lone undotted letter as an initial, so the
injected "wint e r." merged with the sentence after it and the paragraph collapsed to ONE sentence --
burstiness needs two, so the detector abstained and every Zs character read 0.0000 alike. Fixing that
merge (def51c8) split the paragraph correctly again and the shared figure became 0.5545.

The argument this file makes is unchanged by that, because the argument was never about the value:
a plain space moves the score exactly as much as every exotic space does, so movement alone is not
evidence of a defect. Pinning the number instead of the property made a correct fix look like a
regression.

**The Zl/Zp rows are deliberate.** They are line breaks, so `scrub` maps them to a newline rather than
deleting them — deleting one welds two lines together, which is the damage the layout work in this
repository exists to prevent. The text after scrubbing genuinely contains line breaks, so its score
genuinely differs.

So the coverage is complete: of the 78 non-space characters, 76 round-trip exactly and 2 are
converted on purpose.
"""

from __future__ import annotations

import logging
import unicodedata

import pytest

from untell.attacks.unicode_tricks import scrub_hidden
from untell.scripts.score import _INVISIBLE_RE, score_text

BASE = (
    "Salt lowers the freezing point of water, which is why councils spread it on roads in winter. "
    "It works down to about minus nine degrees, below which other chemicals are needed instead."
)
# Every Zs character in the BMP. The test below asserts they all move the score identically to a
# plain U+0020, which is the claim that makes the Zs rows a probe artifact rather than a defect.
EXOTIC_SPACES = [
    chr(c) for c in range(0x10000) if unicodedata.category(chr(c)) == "Zs"
]

# One representative per family, plus the two that were missing.
SAMPLE = ["​", "‍", "⁠", "﻿", "­", "؜", "᠎", ""]
SEPARATORS = [" ", " "]


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


@pytest.fixture(scope="module")
def baseline() -> float:
    return score_text(BASE, tier="lite")["max"]


@pytest.mark.parametrize("ch", SAMPLE, ids=[hex(ord(c)) for c in SAMPLE])
def test_a_hidden_character_is_scrubbed_back_to_the_baseline(ch: str, baseline: float) -> None:
    """The property that matters: after a scrub the score is the score of the clean text."""
    injected = BASE.replace("e", "e" + ch)
    cleaned = scrub_hidden(injected)
    assert ch not in cleaned
    assert score_text(cleaned, tier="lite")["max"] == pytest.approx(baseline, abs=0.01)


@pytest.mark.parametrize("ch", SEPARATORS, ids=["U+2028", "U+2029"])
def test_a_line_separator_becomes_a_line_break(ch: str) -> None:
    """Not deleted, converted. Deleting one welds two lines together — and the score after
    conversion legitimately differs, because the text legitimately contains line breaks."""
    cleaned = scrub_hidden("first line" + ch + "second line")
    assert ch not in cleaned
    assert "\n" in cleaned


@pytest.mark.parametrize("ch", SEPARATORS + SAMPLE[:5], ids=lambda c: hex(ord(c)))
def test_the_warning_names_it(ch: str) -> None:
    """`_INVISIBLE_RE` is what the caveat consults, so a character the scrubber handles and the
    caveat does not is only half-covered — which is exactly what U+2028 was."""
    assert _INVISIBLE_RE.search(ch), unicodedata.name(ch, hex(ord(ch)))


def test_ordinary_prose_is_untouched(baseline: float) -> None:
    """Guards the guard. A scrubber that mangled clean text would satisfy nothing above but would be
    a far worse defect than the one this file is about."""
    assert scrub_hidden(BASE) == BASE
    assert score_text(BASE, tier="lite")["max"] == pytest.approx(baseline, abs=1e-9)


def test_a_plain_space_is_not_claimed_as_a_defect(baseline: float) -> None:
    """The probe error this file records, asserted as the property rather than the figure.

    Inserting U+0020 splits words and moves the score — by exactly as much as every exotic space
    moves it — so a sweep that counts "score moved" as a finding reports seventeen defects and has
    none. The scrubber's job is to normalise the character, not to undo the sentence.

    This used to assert `max < 0.01`, which was the shared figure at the time and an artifact of a
    splitting bug rather than a fact about spaces (see the module docstring). When that bug was
    fixed the figure moved and a correct change looked like a regression. What the argument
    actually needs is that the plain space and the exotic spaces land on the SAME value, whatever
    that value is, and that it is not the baseline — which is strictly stronger than the old bound
    and cannot be invalidated by an unrelated improvement.
    """
    injected = BASE.replace("e", "e ")
    plain = score_text(injected, tier="lite")["max"]

    assert plain != pytest.approx(baseline, abs=1e-9), (
        "premise: a plain space must MOVE the score, or there is no probe error to record"
    )
    for ch in EXOTIC_SPACES:
        exotic = score_text(BASE.replace("e", "e" + ch), tier="lite")["max"]
        assert exotic == pytest.approx(plain, abs=1e-9), (
            f"U+{ord(ch):04X} moved the score differently from a plain space "
            f"({exotic} vs {plain}) — the Zs rows would then be a real finding, not a probe artifact"
        )
    assert scrub_hidden(injected) == injected
