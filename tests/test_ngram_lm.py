"""The perplexity signal must stay a signal, and must not quietly become a detector.

`eval/ngram_lm.py` exists because untell's lite tier calls a 120-word stoplist ratio "perplexity",
and nothing in the repository could check that against real perplexity without a model download
that this environment blocks. NLTK's corpora are reachable where model hubs are not, so the check
is a two-million-token bigram model rather than an assumption.

MEASURED 2026-09-01 with it, mean log-perplexity, lower = more predictable = machine-like end:

    ELLIPSE   low proficiency 6.5816   high proficiency 6.4406   d -0.320
    ASAP      ELL             7.0837   non-ELL          6.8778   d -0.491

Both say the more fluent writer is the more predictable one, which is the OPPOSITE of what the
stoplist proxy says. The tests below guard the two ways that finding could be misused: by dropping
the limitation that makes it honest, and by treating a weak bigram LM as a verdict about a text.
"""

from __future__ import annotations

import math

import pytest

from eval.ngram_lm import LAMBDA, MIN_TOKENS, NgramLM, cohen_d, contrast, train


@pytest.fixture(scope="module")
def toy_lm():
    """A tiny hand-built model: predictable text should score below surprising text."""
    common = ["the", "cat", "sat", "on", "the", "mat"] * 200
    uni = {}
    bi = {}
    for w in ["<s>", *common]:
        uni[w] = uni.get(w, 0) + 1
    seq = ["<s>", *common]
    for a, b in zip(seq, seq[1:]):
        bi[(a, b)] = bi.get((a, b), 0) + 1
    return NgramLM({"uni": uni, "bi": bi, "ntok": len(seq), "V": len(uni)})


class TestTheSignalPointsTheRightWay:
    def test_predictable_text_scores_lower_than_surprising_text(self, toy_lm):
        """Lower log-perplexity must mean MORE predictable, or every reading inverts."""
        predictable = toy_lm.log_perplexity("the cat sat on the mat the cat sat on the mat")
        surprising = toy_lm.log_perplexity(
            "zygote quixotic pneumatic yacht xylophone jodhpurs quagmire "
            "obelisk syzygy triskelion"
        )
        assert predictable is not None and surprising is not None
        assert predictable < surprising, (
            f"predictable text scored {predictable:.3f} and surprising text {surprising:.3f}; "
            f"the sign convention is inverted and every published reading flips with it"
        )

    def test_short_text_opts_out_rather_than_guessing(self, toy_lm):
        assert toy_lm.log_perplexity("the cat") is None
        assert toy_lm.log_perplexity("") is None

    def test_the_minimum_is_enforced_at_the_documented_length(self, toy_lm):
        assert toy_lm.log_perplexity(" ".join(["the"] * (MIN_TOKENS - 3))) is None
        assert toy_lm.log_perplexity(" ".join(["the"] * (MIN_TOKENS + 5))) is not None

    def test_an_unseen_word_does_not_produce_infinity(self, toy_lm):
        """Zero probability would make one out-of-vocabulary word swamp the whole document."""
        score = toy_lm.log_perplexity("the cat sat on the mat " + "grobnitz " * 10)
        assert score is not None and math.isfinite(score)

    def test_interpolation_actually_uses_the_bigram(self):
        assert 0 < LAMBDA < 1, "a lambda of 0 or 1 collapses the model to one order"


class TestItRefusesToBeMisread:
    def test_every_contrast_carries_its_limitation(self):
        rows = [{"text": "the cat sat on the mat and then it sat again", "g": "a"}] * 40
        rows += [{"text": "quixotic pneumatic yacht xylophone jodhpurs syzygy obelisk", "g": "b"}] * 40
        lm = NgramLM({"uni": {"the": 10, "cat": 5}, "bi": {("the", "cat"): 5},
                      "ntok": 15, "V": 2})
        out = contrast(rows, lm, "g")
        assert "limitation" in out and "not a detector" in out["limitation"].lower()
        assert "citation" in out and "nltk" in out["citation"].lower()

    def test_missing_values_are_not_a_group(self):
        """Shares the audit's missing-data rule; a bucket of unknowns is not a population."""
        rows = ([{"text": "the cat sat on the mat and then it sat again", "g": "NA"}] * 40
                + [{"text": "the cat sat on the mat and then it sat again", "g": "real"}] * 40)
        lm = NgramLM({"uni": {"the": 10}, "bi": {}, "ntok": 10, "V": 1})
        out = contrast(rows, lm, "g")
        assert "NA" not in out["groups"]

    def test_a_group_below_the_floor_is_not_reported(self):
        rows = ([{"text": "the cat sat on the mat and then it sat again", "g": "tiny"}] * 5
                + [{"text": "the cat sat on the mat and then it sat again", "g": "big"}] * 40)
        lm = NgramLM({"uni": {"the": 10}, "bi": {}, "ntok": 10, "V": 1})
        out = contrast(rows, lm, "g")
        assert "tiny" not in out["groups"] and "big" in out["groups"]


class TestCohenD:
    def test_identical_arms_are_zero(self):
        assert cohen_d([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == 0.0

    def test_direction_is_second_minus_first(self):
        assert cohen_d([1.0, 1.1, 0.9], [2.0, 2.1, 1.9]) > 0

    def test_degenerate_arms_return_none_rather_than_dividing_by_zero(self):
        assert cohen_d([1.0], [2.0, 3.0]) is None
        assert cohen_d([1.0, 1.0, 1.0], [1.0, 1.0, 1.0]) is None


def test_training_on_nothing_is_empty_rather_than_wrong(tmp_path):
    model = train(tmp_path, patterns=("nothing/*",))
    assert model["ntok"] == 0 and model["V"] == 0 and model["files"] == 0
