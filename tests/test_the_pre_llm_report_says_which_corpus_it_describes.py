"""A false-positive rate is meaningless without the corpus definition that produced it.

Round thirty-four established that the outlier gap depended on where the margin line was drawn.
Round thirty-five found the same defect one level down, in the number this repository quotes most
often. `pre_llm_abstracts` takes a `min_words` floor, and the false-positive rate moves with it —
MEASURED at n = 300 each: **22.0% at 30 words, 22.7% at 60, 18.3% at 100, 14.3% at 150**. That is an
8.4-point swing from a parameter no document mentioned, and it is not noise: it is the length effect
this repo already published (30.0% flagged at <=50 words against 13.3% at 200+) reaching the headline
through the corpus floor.

The report used to carry none of it. A saved JSON result named a tier and a count and nothing about
which text it had scored, so two runs could not be compared and neither could be reproduced. These
tests hold the corpus definition to the number.
"""

from __future__ import annotations

import json

import pytest

from eval import pre_llm_fpr


def _run(args: list[str], capsys) -> dict:
    assert pre_llm_fpr.main(args) == 0
    return json.loads(capsys.readouterr().out)


needs_corpus = pytest.mark.skipif(
    not pre_llm_fpr.pre_llm_abstracts(__import__("pathlib").Path(".anthology-cache")),
    reason="pre-LLM corpus not cached (run `python -m eval.litreview --download`)",
)


@needs_corpus
def test_the_json_report_records_the_corpus_definition(capsys):
    report = _run(["--n", "12", "--json"], capsys)
    corpus = report["corpus"]
    for key in ("min_words", "max_year", "seed", "n_available", "n_requested"):
        assert key in corpus, f"a saved report cannot be reproduced without `{key}`"


@needs_corpus
def test_the_recorded_floor_is_the_one_that_was_used(capsys):
    """A field that always says 60 would be worse than no field."""
    report = _run(["--n", "12", "--min-words", "120", "--json"], capsys)
    assert report["corpus"]["min_words"] == 120


@needs_corpus
def test_the_by_length_report_records_it_too(capsys):
    """The length breakdown is the analysis most obviously conditional on a word floor, so it was
    the one most likely to be read without one."""
    report = _run(["--n", "12", "--by-length", "--json"], capsys)
    assert "corpus" in report


@needs_corpus
def test_the_human_readable_output_names_the_floor_and_its_effect(capsys):
    """Someone reading the terminal gets the number. They must also get the sentence saying the
    number moves with a setting they did not choose."""
    assert pre_llm_fpr.main(["--n", "12"]) == 0
    out = capsys.readouterr().out
    assert "60+ words" in out
    assert "word floor moves this number" in out


@needs_corpus
def test_a_higher_floor_really_does_change_which_texts_are_scored(capsys):
    """The reason the field matters, tested rather than asserted. If the floor did nothing, recording
    it would be ceremony."""
    from pathlib import Path

    cache = Path(".anthology-cache")
    low = pre_llm_fpr.pre_llm_abstracts(cache, min_words=30)
    high = pre_llm_fpr.pre_llm_abstracts(cache, min_words=150)
    assert len(high) < len(low), "a higher word floor must exclude texts"
    assert all(len(t.split()) >= 150 for t in high)
