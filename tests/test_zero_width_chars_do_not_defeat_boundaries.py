"""Zero-width characters must not defeat a sentence boundary.

A zero-width space (or any invisible carrier) sitting between a full stop and the next
word is invisible to ``\\s``, so ``(?<=[.!?])\\s+`` refused to split and the two sentences
were scored, burstinessed and rewritten as one:

    split_sentences('Done.\u200bNext sentence.')   -> ONE sentence
    split_sentences('Done.\u200b Next sentence.')  -> ONE sentence

Same class on the merge rules: a trailing zero-width char after an ellipsis or a quoted
period made the continuation look like a new sentence, and after an abbreviation it hid
the abbreviation from ``ends_with_abbreviation``.

The splitter does NOT remove these characters (they may be load-bearing elsewhere, e.g.
ZWJ in emoji); it only refuses to let them hide a boundary.
"""

from untell.text_split import split_sentences

ZWSP = "\u200b"
ZWNJ = "\u200c"
BOM = "\ufeff"


def test_zwsp_between_terminator_and_word_is_not_a_boundary_blocker():
    assert split_sentences(f"Done.{ZWSP}Next sentence.") == [f"Done.{ZWSP}", "Next sentence."]


def test_zwsp_then_space_splits_too():
    assert split_sentences(f"Done.{ZWSP} Next sentence.") == [f"Done.{ZWSP}", "Next sentence."]


def test_two_zero_width_chars_still_split():
    assert split_sentences(f"Done.{ZWSP}{BOM}Next sentence.") == [
        f"Done.{ZWSP}{BOM}",
        "Next sentence.",
    ]


def test_abbreviation_tail_with_zero_width_char_is_still_recognised():
    # The abbreviation's period must still be recognised with a ZWSP after it: 'p.m.'
    # ends the sentence, and the capital 'Then' opens the next one — the same split the
    # plain 'p.m. Then' case produces, instead of the whole thing merging into one.
    parts = split_sentences(f"The meeting is at 3 p.m.{ZWSP} Then we left.")
    assert len(parts) == 2, parts
    assert parts[0] == f"The meeting is at 3 p.m.{ZWSP}"
    assert parts[1] == "Then we left."


def test_ellipsis_continuation_merges_across_a_zero_width_char():
    # '...' is a pause, not a terminator: a lowercase continuation is the same clause even
    # with a zero-width char after the dots.
    parts = split_sentences(f"He paused...{ZWSP} then continued with the analysis.")
    assert len(parts) == 1, parts


def test_quoted_period_continuation_merges_across_a_zero_width_char():
    parts = split_sentences(f'He said "stop."{ZWSP} and left.')
    assert len(parts) == 1, parts


def test_zwnj_does_not_block_a_boundary_either():
    assert split_sentences(f"Really?{ZWNJ} Yes.") == [f"Really?{ZWNJ}", "Yes."]
