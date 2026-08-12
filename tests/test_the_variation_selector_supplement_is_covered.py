"""U+E0100–U+E01EF is 240 invisible codepoints, and no test mentioned any of them.

Swept 30 hidden-character carrier classes through `count_hidden` and `scrub_hidden`. The surface
is sound — 26 of 30 counted, 29 of 30 fully scrubbed, and every apparent miss checked out as
deliberate:

  * a lone combining acute is not hidden, it is how "é" is written
  * fullwidth and mathematical-bold letters are visible glyphs, not carriers
  * a stack of 8 combining marks scrubs to 4 and reports 4 removed — one of those 4 then composes
    into "é" under NFC, which is why only 3 standalone marks remain in the output

Then checked which carriers the suite actually names. Every one had a test except the Variation
Selector Supplement: U+2060, U+FEFF, U+180E, U+17B4, U+FFF9, U+2066, U+2007, U+200A and U+3000 all
appear in tests/, and U+E0100 appeared in none.

It works today — the block is handled by the same rule as U+FE00–U+FE0F. What was missing is
anything that would notice if that stopped being true, and a 240-codepoint invisible block is
exactly what a watermarker reaches for after the obvious ones are closed.
"""
from __future__ import annotations

import pytest

from untell.attacks import count_hidden, scrub_hidden

BLOCK = [0xE0100, 0xE0110, 0xE01EF]  # first, middle, last of the supplement


@pytest.mark.parametrize("codepoint", BLOCK, ids=[f"U+{c:04X}" for c in BLOCK])
def test_a_supplement_selector_is_counted(codepoint: int):
    text = f"hello{chr(codepoint)} world here"
    counted = count_hidden(text)
    total = sum(v for v in counted.values() if isinstance(v, int)) if isinstance(counted, dict) else counted
    assert total >= 1, f"U+{codepoint:04X} was not reported as hidden: {counted}"


@pytest.mark.parametrize("codepoint", BLOCK, ids=[f"U+{c:04X}" for c in BLOCK])
def test_a_supplement_selector_is_removed(codepoint: int):
    text = f"hello{chr(codepoint)} world here"
    assert chr(codepoint) not in scrub_hidden(text)


def test_a_run_of_them_is_removed_entirely():
    """A payload is a run, not one character. Trimming to a plausible maximum would leave data."""
    payload = "".join(chr(0xE0100 + i) for i in range(20))
    text = f"hello{payload} world here"
    cleaned = scrub_hidden(text)
    assert not any(0xE0100 <= ord(c) <= 0xE01EF for c in cleaned), (
        "part of the payload survived; unlike combining marks, nothing legitimate stacks these"
    )


def test_scrubbing_reports_clean_afterwards():
    """The failure that matters is not a missed character, it is a missed character reported clean."""
    text = "hello" + "".join(chr(0xE0100 + i) for i in range(5)) + " world here"
    cleaned = scrub_hidden(text)
    counted = count_hidden(cleaned)
    total = sum(v for v in counted.values() if isinstance(v, int)) if isinstance(counted, dict) else counted
    assert total == 0, f"scrubbed text still reports hidden characters: {counted}"


def test_visible_text_is_untouched():
    text = "hello world here"
    assert scrub_hidden(text) == text
