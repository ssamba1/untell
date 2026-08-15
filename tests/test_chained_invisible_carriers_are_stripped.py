"""Chained invisible carriers must not survive scrub_hidden.

Two order/neighbour defects in the contextual carrier rules, both verified before the fix:

1. ``scrub_hidden('a\\uFE00\\uFE00b')`` returned ``'a\\uFE00b'`` — of two consecutive
   variation selectors between Latin letters, the second survived. The neighbour test saw
   the FIRST (dropped) VS as an "emoji-adjacent" base (0xFE00-0xFE0F is in
   ``_is_emoji_adjacent``), so every VS after the first is judged attached.

2. ``scrub_hidden('a\\uFE0F\\u200D\\uFE0Fb')`` returned ``'a\\u200db'`` — an orphan ZWJ
   survived because ``_strip_orphan_zwj`` ran BEFORE the VS strip, so the ZWJ's neighbours
   were still the (later-dropped) VS16s and it was judged to be joining emoji.

Both violate the module's own promise: a VS or ZWJ between two Latin letters is a carrier
and is dropped. The legitimate emoji shapes (families, keycaps, flags, hearts, ZWJ
sequences) must stay byte-identical.
"""

from untell.attacks.unicode_tricks import count_hidden, scrub_hidden

VS16 = "\ufe0f"
VS1 = "\ufe00"


def test_two_consecutive_variation_selectors_between_letters_are_both_stripped():
    assert scrub_hidden(f"a{VS1}{VS1}b") == "ab"


def test_mixed_variation_selectors_between_letters_are_both_stripped():
    assert scrub_hidden(f"a{VS1}{VS16}b") == "ab"


def test_vs_zwj_vs_carrier_is_fully_removed():
    # VS+ZWJ+VS: with VS stripped first, the ZWJ's neighbours are plain letters and it is
    # an orphan carrier, not an emoji joiner.
    assert scrub_hidden(f"a{VS16}\u200d{VS16}b") == "ab"


def test_zwj_vs_trailing_carrier_is_removed():
    assert scrub_hidden(f"ab\u200d{VS16}") == "ab"


def test_count_hidden_counts_every_chained_vs():
    assert count_hidden(f"a{VS1}{VS1}b") == 2


def test_emoji_family_survives_unchanged():
    family = "\U0001f468\u200d\U0001f469\u200d\U0001f467"
    assert scrub_hidden(family) == family


def test_emoji_with_variation_selector_survives():
    assert scrub_hidden("\u2764\ufe0f") == "\u2764\ufe0f"
    assert scrub_hidden("\U0001f469\u200d\u2695\ufe0f") == "\U0001f469\u200d\u2695\ufe0f"


def test_keycap_survives():
    assert scrub_hidden("press 1\ufe0f\u20e3 to continue") == "press 1\ufe0f\u20e3 to continue"


def test_flag_survives():
    flag = "\U0001f3f3\ufe0f\u200d\U0001f308"
    assert scrub_hidden(flag) == flag


def test_variation_selector_after_emoji_base_is_kept():
    # The FIRST selector after a real emoji base is legitimate and must stay.
    assert scrub_hidden(f"\u2764{VS16}{VS16}") == f"\u2764{VS16}{VS16}"
