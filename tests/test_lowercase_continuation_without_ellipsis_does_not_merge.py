"""A lowercase continuation without an ellipsis must not merge sentences.

text_split.py:95: `_continues_after_ellipsis` requires BOTH an ellipsis-ending
previous fragment AND a lowercase next word. The mutation and -> or makes a
plain lowercase continuation merge ("Hello world. next thing" -> ONE sentence),
silently destroying a sentence boundary the whole pipeline splits on.
"""
from untell.text_split import _continues_after_ellipsis, split_sentences


def test_lowercase_continuation_without_ellipsis_does_not_merge():
    assert _continues_after_ellipsis("Hello world.", "next thing") is False


def test_ellipsis_continuation_merges():
    assert _continues_after_ellipsis("It works...", "mostly") is True


def test_sentence_boundary_preserved_without_ellipsis():
    assert split_sentences("Hello world. next thing") == [
        "Hello world.",
        "next thing",
    ]
