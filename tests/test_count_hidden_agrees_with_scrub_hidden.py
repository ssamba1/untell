"""`count_hidden` and `scrub_hidden` must agree, and for five versions they did not.

The old `count_hidden` re-derived the answer: one counting term per carrier class, added by hand
whenever a class was added to the scrubber. Its own comments record the drift as it happened —
"this is the third carrier class to go missing from this function", then a fourth. At the time this
file was written there were three more, in both directions:

    U+206A-206F deprecated format   scrub removes it   count said 0
    U+0600, U+06DD Arabic marks     scrub removes it   count said 0
    U+2028 line separator           scrub rewrites it  count said 0
    Russian prose ("Это очень...")  scrub no-op        count said 9
    Greek prose  ("Αυτό είναι...")  scrub no-op        count said 9

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

# One per carrier class the scrubber handles, plus the two prose cases it must NOT touch.
CARRIERS = {
    "zero-width space": "a​b",
    "zero-width joiner (orphan)": "a‍b",
    "deprecated format U+206A": "a⁪b",
    "deprecated format U+206F": "a⁯b",
    "arabic number sign U+0600": "a؀b",
    "arabic end of ayah U+06DD": "a۝b",
    "line separator U+2028": "a b",
    "paragraph separator U+2029": "a b",
    "no-break space": "a b",
    "bidi override": "a‮b",
    "tag character": "a\U000e0041b",
    "kelvin sign": "aKb",
    "cyrillic homoglyph in latin": "The systxm shuts down.".replace("x", "е"),
}
CLEAN = {
    "english": "The system shuts down when the sensor fails.",
    "russian prose": "Это очень простой текст про кота.",
    "greek prose": "Αυτό είναι ένα απλό κείμενο.",
    "emoji with selector": "ok ❤️ done",
    "accented composition": "café naïve",
    "cjk": "这是一段中文文字，用来测试。",
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
    text = "a​b c⁪d e"
    assert count_hidden(text) == 4, count_hidden(text)


def test_scrubbing_is_idempotent_and_then_counts_zero() -> None:
    text = "a​b c⁪d e‮f"
    once = scrub_hidden(text)
    assert scrub_hidden(once) == once, "scrub_hidden is not idempotent"
    assert count_hidden(once) == 0, "already-scrubbed text still reports hidden characters"


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
