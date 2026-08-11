"""Combining marks were the one invisible-carrier class never swept.

`scrub_hidden` was verified exhaustively against every Cf and Cc codepoint. Category Mn was not:
a 24-mark stack on a single base character survived the scrub intact and `count_hidden` reported
**0**, so the tool said the text was clean while the payload rode through untouched. That is the
same shape this module already recorded twice — once for 49 scripted format marks, once for NFC
singletons — in the codepoint class it had not looked at.

They cannot be filtered by identity: the exact codepoints that carry a payload are the ones that
write Hebrew, Thai and Devanagari. So the rule is stack DEPTH, and these tests pin both sides of
it — the payload dies, the languages survive.
"""

from __future__ import annotations

import unicodedata

import pytest

from untell.attacks import scrub_hidden
from untell.attacks.unicode_tricks import _MAX_MARK_STACK, count_hidden

BASE = "The quick brown fox jumps over the lazy dog."


def _payload(n: int) -> str:
    return BASE[:10] + "".join(chr(0x0300 + (i % 16)) for i in range(n)) + BASE[10:]


def _marks(text: str) -> int:
    return sum(1 for ch in text if unicodedata.category(ch) == "Mn")


def test_a_stacked_payload_does_not_survive_the_scrub():
    scrubbed = scrub_hidden(_payload(24))
    assert _marks(scrubbed) <= _MAX_MARK_STACK, "the stack must be cut to the legitimate depth"


def test_a_stacked_payload_is_not_reported_clean():
    """The worse half of the bug: the count said 0 while 24 carrier codepoints were present."""
    assert count_hidden(_payload(24)) == 24 - _MAX_MARK_STACK


def test_the_count_matches_what_the_scrub_actually_removes():
    """The invariant this module states for every carrier class."""
    for n in (0, 1, _MAX_MARK_STACK, _MAX_MARK_STACK + 1, 12, 40):
        text = _payload(n)
        removed = _marks(text) - _marks(scrub_hidden(text))
        assert removed == max(0, n - _MAX_MARK_STACK), f"n={n}: scrub removed {removed}"


# Real text in the scripts that stack marks most heavily. Measured maximum depth after NFC:
# hebrew 3, devanagari 2, thai 2, arabic 2 — all at or below the cutoff.
DIACRITIC_SCRIPTS = {
    "vietnamese": "Tiếng Việt rất đẹp và phong phú, nhiều người học nó mỗi ngày.",
    "devanagari": "हिन्दी भारत की राजभाषा है और करोड़ों लोग इसे बोलते हैं।",
    "thai": "ภาษาไทยเป็นภาษาราชการของประเทศไทยและมีผู้พูดจำนวนมาก",
    "arabic_diacritics": "بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ",
    "hebrew_niqqud": "בְּרֵאשִׁית בָּרָא אֱלֹהִים אֵת הַשָּׁמַיִם",
}


@pytest.mark.parametrize("name", sorted(DIACRITIC_SCRIPTS))
def test_a_language_that_uses_marks_is_left_alone(name: str):
    """The failure mode to avoid: the blanket homoglyph map once destroyed Russian this way."""
    text = DIACRITIC_SCRIPTS[name]
    assert scrub_hidden(text) == unicodedata.normalize("NFC", text)
    assert count_hidden(text) == 0


def test_the_cutoff_has_headroom_over_every_script_measured():
    deepest = 0
    for text in DIACRITIC_SCRIPTS.values():
        run = 0
        for ch in unicodedata.normalize("NFC", text):
            run = run + 1 if unicodedata.category(ch) == "Mn" else 0
            deepest = max(deepest, run)
    assert deepest < _MAX_MARK_STACK, f"deepest legitimate stack {deepest} vs cutoff {_MAX_MARK_STACK}"


def test_plain_text_is_untouched():
    assert scrub_hidden(BASE) == BASE
    assert count_hidden(BASE) == 0


def test_marks_on_separate_bases_are_not_a_stack():
    """Depth, not total count — one mark each on many characters is ordinary accented text."""
    spread = "".join(f"{ch}́" if ch.isalpha() else ch for ch in "abc def ghi")
    assert count_hidden(spread) == 0
    assert _marks(scrub_hidden(spread)) == _marks(unicodedata.normalize("NFC", spread))


def test_enclosing_marks_stack_too():
    """Category Me is the same construct as Mn; testing only "Mn" left all 13 unlimited."""
    payload = BASE[:10] + "҈" * 20 + BASE[10:]
    scrubbed = scrub_hidden(payload)
    assert scrubbed.count("҈") <= _MAX_MARK_STACK
    assert count_hidden(payload) == 20 - _MAX_MARK_STACK


def test_an_emoji_keycap_survives():
    """The one legitimate enclosing mark: base + VS16 + U+20E3 is a stack of one."""
    for keycap in ("1️⃣", "7️⃣", "#️⃣"):
        text = f"press {keycap} to continue"
        assert keycap in scrub_hidden(text), f"{keycap!r} was mangled"


def test_private_use_and_unassigned_are_left_alone_on_purpose():
    """Documented scope limit: tofu-rendering, font-load-bearing, and Unicode-version dependent."""
    for ch in ("", "", "͸"):
        text = f"icon {ch} here"
        assert ch in scrub_hidden(text)
