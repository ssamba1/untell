"""A dictionary abbreviation must not end a sentence.

text_split.py:55 returns True for words in the abbreviation dictionary. The
mutation True -> False makes "Dr." fall through to the length/parts heuristic,
where "dr" (2 chars, one part) fails `any(len(p) > 1)` and is treated as a
sentence ender — splitting "Dr. Smith arrived." into "Dr." + "Smith arrived."
This test pins the dict lookup.
"""
from untell.text_split import split_sentences


def test_dict_abbreviation_does_not_end_a_sentence():
    assert split_sentences("Dr. Smith arrived. The test began.") == [
        "Dr. Smith arrived.",
        "The test began.",
    ]


def test_dotted_abbreviation_list_stays_one_sentence():
    # J.R.R. Tolkien — the dotted-initial path (line 60) also must not split.
    assert split_sentences("J.R.R. Tolkien wrote the book.") == [
        "J.R.R. Tolkien wrote the book."
    ]
