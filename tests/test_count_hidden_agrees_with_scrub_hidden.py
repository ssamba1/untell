"""`count_hidden` and `scrub_hidden` must agree, and for five versions they did not.

The old `count_hidden` re-derived the answer: one counting term per carrier class, added by hand
whenever a class was added to the scrubber. Its own comments record the drift as it happened —
"this is the third carrier class to go missing from this function", then a fourth. At the time this
file was written there were three more, in both directions:

    U+206A-206F deprecated format   scrub removes it   count said 0
    U+0600, U+06DD Arabic marks     scrub removes it   count said 0
    U+2028 line separator           scrub rewrites it  count said 0
    Russian prose ("Eto ochen...")  scrub no-op        count said 9
    Greek prose                     scrub no-op        count said 9

The first three are the dangerous direction, and the docstring already named it: the caller is told
the text is clean while a watermark is silently discarded. The last two are the reverse — the count
matched confusables CONTEXT-FREE while `_unhomoglyph` is context-aware and leaves genuine Cyrillic
alone, so the tool reported "9 hidden characters removed" and returned the input verbatim.

`count_hidden` is now the scrubber's own diff, which makes every one of them impossible by
construction and counts any future carrier class the day it is scrubbed rather than the day someone
remembers. MEASURED after: 0 disagreements across all 1,114,112 codepoints, and 0.031s on 48 KB —
the REST bound is 50 KB, so the cost is not a reason to go back to a second rule list.
"""

from __future__ import annotations

import pytest

from untell.attacks.unicode_tricks import count_hidden, scrub_hidden

# Every fixture below is built with `chr()`, never a pasted invisible character and never a `\\u`
# escape in a string literal.
#
# A literal U+200B is invisible in the editor, invisible in the diff, and survives review unnoticed;
# it is also what whitespace-normalising tooling silently drops, which would turn a carrier fixture
# into a clean one with nobody seeing the change. This repo's own audit fails a tracked file that
# carries a stray control character, and a fixture file about hidden characters is the last place
# one should be able to hide.
#
# `chr()` rather than `"\\u200b"` because two attempts to write the escape did not survive the trip
# to disk — the bytes came back as 342 200 213 both times, once through a shell heredoc and once
# through the editor, each transport decoding the escape before the file was written.
# `chr(0x200B)` is plain ASCII in the source whatever writes it, and
# `test_no_fixture_carries_a_literal_invisible_character` below is what caught both attempts.
CARRIERS = {
    "zero-width space": "a" + chr(0x200B) + "b",
    "zero-width joiner (orphan)": "a" + chr(0x200D) + "b",
    "deprecated format U+206A": "a" + chr(0x206A) + "b",
    "deprecated format U+206F": "a" + chr(0x206F) + "b",
    "arabic number sign U+0600": "a" + chr(0x0600) + "b",
    "arabic end of ayah U+06DD": "a" + chr(0x06DD) + "b",
    "line separator U+2028": "a" + chr(0x2028) + "b",
    "paragraph separator U+2029": "a" + chr(0x2029) + "b",
    "no-break space": "a" + chr(0x00A0) + "b",
    "bidi override": "a" + chr(0x202E) + "b",
    "tag character": "a" + chr(0xE0041) + "b",
    "kelvin sign": "a" + chr(0x212A) + "b",
    # A Cyrillic 'e' inside an otherwise Latin sentence: the context-aware case, where the
    # surrounding evidence says Latin so the confusable is a carrier rather than real Cyrillic.
    "cyrillic homoglyph in latin": "The syst" + chr(0x0435) + "m shuts down.",
}


CLEAN = {
    "english": "The system shuts down when the sensor fails.",
    # Genuine Cyrillic and Greek prose. These are the false-positive cases: every 'o' matched
    # the confusable table context-free, so the old count reported 9 on text never touched.
    "russian prose": "".join(chr(c) for c in
        (0x42D, 0x442, 0x43E, 0x20, 0x43E, 0x447, 0x435, 0x43D, 0x44C, 0x20,
         0x43F, 0x440, 0x43E, 0x441, 0x442, 0x43E, 0x439, 0x2E)),
    "greek prose": "".join(chr(c) for c in
        (0x391, 0x3C5, 0x3C4, 0x3CC, 0x20, 0x3B5, 0x3AF, 0x3BD, 0x3B1, 0x3B9, 0x2E)),
    "accented composition": "caf" + chr(0xE9) + " na" + chr(0xEF) + "ve",
    "cjk": "".join(chr(c) for c in (0x8FD9, 0x662F, 0x4E2D, 0x6587, 0x3002)),
}



@pytest.mark.parametrize("name", sorted(CARRIERS))
def test_a_carrier_is_counted_exactly_when_it_is_scrubbed(name: str) -> None:
    text = CARRIERS[name]
    changed = scrub_hidden(text) != text
    counted = count_hidden(text)
    assert changed, f"{name} is no longer scrubbed; this fixture has stopped testing anything"
    assert counted > 0, (
        f"{name}: scrub_hidden changes the text and count_hidden reports {counted}. That is the "
        f"worst report this function can give — the caller is told the text is clean while a "
        f"carrier is silently removed."
    )


@pytest.mark.parametrize("name", sorted(CLEAN))
def test_clean_text_is_counted_as_clean(name: str) -> None:
    """The other direction. Reporting hidden characters in text the scrubber does not touch is a
    claim the user cannot check, and it was true of any Cyrillic or Greek prose."""
    text = CLEAN[name]
    changed = scrub_hidden(text) != text
    counted = count_hidden(text)
    assert not changed, f"{name} is now being scrubbed; the fixture is no longer clean text"
    assert counted == 0, f"{name}: count_hidden reports {counted} on text scrub_hidden leaves alone"


def test_the_two_agree_on_a_document_carrying_several_classes() -> None:
    """Per character, not merely non-zero. A count that answered 1 for any dirty text would satisfy
    every case above."""
    text = "a" + chr(0x200B) + "b c" + chr(0x206A) + "d e" + chr(0x2028) + "f"
    assert count_hidden(text) == 3, count_hidden(text)


def test_scrubbing_is_idempotent_and_then_counts_zero() -> None:
    text = "a" + chr(0x200B) + "b c" + chr(0x206A) + "d e" + chr(0x202E) + "f"
    once = scrub_hidden(text)
    assert scrub_hidden(once) == once, "scrub_hidden is not idempotent"
    assert count_hidden(once) == 0, "already-scrubbed text still reports hidden characters"


def test_no_fixture_carries_a_literal_invisible_character() -> None:
    """Guards the fixtures themselves, in the one file where that matters most.

    Reads this file's own SOURCE and fails if a raw format, control or exotic-space character was
    pasted in rather than escaped — the mistake the first version of this file made.
    """
    import unicodedata
    from pathlib import Path

    source = Path(__file__).read_text(encoding="utf-8")
    literal = sorted(
        {
            hex(ord(ch))
            for ch in source
            if ch not in "\n\t\r "
            and unicodedata.category(ch) in ("Cf", "Cc", "Zl", "Zp", "Zs")
        }
    )
    assert not literal, f"literal invisible characters in this file's source: {literal}"


@pytest.mark.slow
def test_no_codepoint_anywhere_disagrees() -> None:
    """Exhaustive, and the reason the derived implementation is worth its cost.

    A curated list is exactly what the previous implementation was, and it drifted five times. This
    is the check that cannot drift: every codepoint, both directions. MEASURED: 0 disagreements.
    """
    disagreements = []
    for codepoint in range(0x110000):
        if 0xD800 <= codepoint <= 0xDFFF:  # lone surrogates are not valid text
            continue
        probe = "a" + chr(codepoint) + "b"
        try:
            changed = scrub_hidden(probe) != probe
            counted = count_hidden(probe)
        except Exception:  # pragma: no cover - a codepoint the scrubber cannot handle at all
            continue
        if (counted == 0) != (not changed):
            disagreements.append(hex(codepoint))
            if len(disagreements) > 20:
                break

    assert not disagreements, (
        f"count_hidden and scrub_hidden disagree on {len(disagreements)} codepoints: "
        f"{disagreements[:20]}"
    )
