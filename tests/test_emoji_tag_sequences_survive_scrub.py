"""Emoji tag sequences (England/Scotland/Wales flags) must survive scrub_hidden.

The blanket ``[\\U000e0000-\\U000e007f]`` branch of ``_WATERMARK_CHARS`` treated every
tag character as an invisible watermark carrier. That is true of a LONE tag char, and
false of a tag char inside an emoji TAG SEQUENCE: the England flag 🏴󠁧󠁢󠁥󠁮󠁧󠁿 is
U+1F3F4 (WAVING BLACK FLAG) + tag letters g b e n g + U+E007F CANCEL TAG, and the
Scotland and Wales flags are the same shape. Stripping the tags turned a legitimate
flag emoji into a bare black flag — a rendering change to real content, the exact
failure the module's ZWJ and variation-selector rules already exist to prevent.

MEASURED before the fix:

    scrub_hidden("Team 🏴󠁧󠁢󠁥󠁮󠁧󠁿 won")   ->  "Team 🏴 won"      (England flag destroyed)
    scrub_hidden("Team 🏴󠁧󠁢󠁳󠁣󠁴󠁿 won")   ->  "Team 🏴 won"      (Scotland flag destroyed)
    count_hidden("Team 🏴󠁧󠁢󠁥󠁮󠁧󠁿 won")  ->  6                 (reported as 6 hidden chars)

Same rule as the bidi marks, one level up: a tag char inside a COMPLETE tag sequence
(base + tags + CANCEL TAG) is load-bearing and survives; anywhere else it is payload
and is stripped.
"""

from __future__ import annotations

import pytest

from untell.attacks.unicode_tricks import count_hidden, scrub_hidden

# U+1F3F4 WAVING BLACK FLAG + tag letters g b e n g + U+E007F CANCEL TAG
ENGLAND = "\U0001F3F4\U000E0067\U000E0062\U000E0065\U000E006E\U000E0067\U000E007F"
# U+1F3F4 + g b s c t + CANCEL TAG
SCOTLAND = "\U0001F3F4\U000E0067\U000E0062\U000E0073\U000E0063\U000E0074\U000E007F"
# U+1F3F4 + g b a w l + CANCEL TAG
WALES = "\U0001F3F4\U000E0067\U000E0062\U000E0061\U000E0077\U000E006C\U000E007F"


@pytest.mark.parametrize(
    "name,flag",
    [("England", ENGLAND), ("Scotland", SCOTLAND), ("Wales", WALES)],
    ids=["england", "scotland", "wales"],
)
def test_a_complete_emoji_tag_sequence_survives(name, flag):
    text = f"Team {flag} won the match."
    assert scrub_hidden(text) == text, f"{name} flag was corrupted by scrub_hidden"
    assert count_hidden(text) == 0, f"{name} flag reported {count_hidden(text)} hidden chars"


def test_a_flag_sequence_inside_a_sentence_survives():
    assert scrub_hidden(f"Go {ENGLAND} go!") == f"Go {ENGLAND} go!"


def test_a_lone_tag_character_is_still_stripped():
    """The carrier case is unchanged: a tag char outside a sequence is payload."""
    tag = "\U000E0061"  # TAG LETTER A
    assert scrub_hidden(f"ab{tag}cd") == "abcd"
    assert count_hidden(f"ab{tag}cd") == 1


def test_tag_chars_without_the_flag_base_are_still_stripped():
    """Tag chars need the WAVING BLACK FLAG base; letters alone are not a sequence."""
    # g b e n g + CANCEL TAG with no base, and a CANCEL TAG alone
    assert scrub_hidden(f"ab\U000E0067\U000E0062\U000E0065\U000E006E\U000E0067\U000E007Fcd") == "abcd"
    assert scrub_hidden(f"ab\U000E007Fcd") == "abcd"


def test_an_incomplete_sequence_is_stripped():
    """A base followed by tags but NO CANCEL TAG is not a complete flag sequence.

    The tags are orphan payload and are stripped; the WAVING BLACK FLAG base is itself
    a legitimate emoji and survives.
    """
    incomplete = "\U0001F3F4\U000E0067\U000E0062\U000E0065\U000E006E\U000E0067"
    assert scrub_hidden(f"ab{incomplete}cd") == "ab\U0001F3F4cd"


def test_scrub_is_idempotent_on_a_flag_sequence():
    once = scrub_hidden(f"Team {ENGLAND} won")
    assert scrub_hidden(once) == once
