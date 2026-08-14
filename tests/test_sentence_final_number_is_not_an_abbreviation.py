"""Digit-only abbreviation semantics: number-whole-fragment, not any-digit.

text_split.py:74: an all-digit abbreviation requires the number to be the WHOLE
fragment ("3.5." as a list marker), so a sentence-final number ("The mean was
3.5.") still ends its sentence. The mutation and -> or makes ANY all-digit
fragment an abbreviation, merging "The mean was 3.5. Variance was low." into
one sentence — the documented PRIOR defect, reintroduced. The == -> != sibling
makes "3.5. Methods" an abbreviation, splitting mid-list-item.
"""
from untell.text_split import ends_with_abbreviation, split_sentences


def test_sentence_final_number_is_not_an_abbreviation():
    assert ends_with_abbreviation("The mean was 3.5.") is False


def test_number_as_whole_fragment_is_a_list_marker_not_sentence_end():
    # "3.5." alone: the fragment IS the number -> ordered-list marker -> no split after it
    assert ends_with_abbreviation("3.5.") is True


def test_decimal_sentence_boundary_preserved():
    assert split_sentences("The mean was 3.5. Variance was low.") == [
        "The mean was 3.5.",
        "Variance was low.",
    ]
