"""A corpus below the tool's own thresholds must announce itself.

Every loader in `eval/datasets.py` filters at `> 30` words. Two of untell's guards sit above that:
`score._MIN_WORDS_FOR_A_VERDICT` is 40, and `tells._MIN_WORDS_FOR_REPETITION` is 60, which gates
the two strongest tell categories. A corpus of 35-word texts produces numbers the tool would
refuse to stand behind if asked about any single document in it.

MEASURED over 40 samples per corpus:

    corpus   median words   under 60
    HC3            207         0%
    RAID           281         0%
    MAGE            37        90%

This explains a result that looked like a coverage hole. The loop moves tells 169 -> 149 on HC3
and 377 -> 298 on RAID but 36 -> 35 on MAGE — because on 90% of MAGE documents the repetition
categories cannot fire at all. The loop was fine; the corpus was short, and nothing said so.

A warning, not a filter: raising the floor would silently change every MAGE figure already
recorded, and `load_pairs` already takes `min_words` for callers who want one.
"""
from __future__ import annotations

import logging

from eval.datasets import _warn_if_mostly_too_short


def test_a_short_corpus_warns(caplog):
    short = ["one two three four five six seven eight nine ten"] * 6  # 10 words each
    with caplog.at_level(logging.WARNING):
        assert _warn_if_mostly_too_short("mage", short) == short
    assert "under 40 words" in caplog.text
    assert "median 10" in caplog.text


def test_a_normal_corpus_stays_quiet(caplog):
    """A caveat on every load is a caveat nobody reads."""
    long_enough = [" ".join(f"word{i}" for i in range(120))] * 6
    with caplog.at_level(logging.WARNING):
        _warn_if_mostly_too_short("hc3", long_enough)
    assert caplog.text == ""


def test_a_minority_of_short_texts_does_not_trip_it(caplog):
    """The bar is a quarter. One short document in a corpus is normal, not a property of it."""
    texts = [" ".join(f"word{i}" for i in range(120))] * 9 + ["too short entirely"]
    with caplog.at_level(logging.WARNING):
        _warn_if_mostly_too_short("hc3", texts)
    assert caplog.text == ""


def test_the_threshold_comes_from_the_scorer_not_a_copy():
    """A local constant would drift from the guard it is meant to mirror."""
    from untell.scripts.score import _MIN_WORDS_FOR_A_VERDICT

    texts = [" ".join(["w"] * (_MIN_WORDS_FOR_A_VERDICT - 1))] * 4
    import logging as _logging

    records = []
    handler = _logging.Handler()
    handler.emit = records.append
    logger = _logging.getLogger("eval.datasets")
    logger.addHandler(handler)
    try:
        _warn_if_mostly_too_short("x", texts)
    finally:
        logger.removeHandler(handler)
    assert records, "text one word under the scorer's own minimum did not warn"


def test_an_empty_corpus_is_not_a_short_one(caplog):
    """Nothing loaded is a different failure, reported elsewhere; warning here would misattribute it."""
    with caplog.at_level(logging.WARNING):
        assert _warn_if_mostly_too_short("mage", []) == []
    assert caplog.text == ""
