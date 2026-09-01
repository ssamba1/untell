"""The transformer perplexity path, and the sanity probe that has to be right.

`eval/gpt2_onnx.py` answers the question left open for most of this work: does a real transformer
show the same correlation as the stdlib bigram model? It does, and more strongly (d -0.671 vs
-0.491 on ASAP; -1.320 vs -0.320 on ELLIPSE).

MEASURED FAILURE this file guards, and it was mine: the first sanity probe compared fluent prose
against a comma-separated list of rare words and expected the list to score HIGHER. It scores
LOWER -- a list of nouns is positionally very predictable to GPT-2 -- so the probe "failed" while
the model was correct, and for a few minutes I believed the packaged module was broken. The right
probe holds the words fixed and changes only the order:

    fluent prose          3.4542
    same words shuffled   7.6787

Model-dependent tests skip when the ~665MB ONNX file is not cached, so CI never downloads it. The
pure logic -- tokenizer, effect size, grouping -- is tested unconditionally.
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from eval.gpt2_onnx import MAX_TOKENS, MIN_TOKENS, Encoder, bytes_to_unicode, cohen_d, contrast

MODEL_DIR = Path.home() / ".cache" / "untell-corpora" / "gpt2"
_HAVE_MODEL = (MODEL_DIR / "gpt2-lm-head.onnx").exists()
needs_model = pytest.mark.skipif(not _HAVE_MODEL, reason="GPT-2 ONNX not cached; run fetch first")


class TestTokenizer:
    def test_byte_encoder_is_a_bijection_over_256_values(self):
        m = bytes_to_unicode()
        assert len(m) == 256
        assert len(set(m.values())) == 256, "two bytes map to one character; BPE would corrupt"

    @pytest.mark.skipif(not (MODEL_DIR / "encoder.json").exists(), reason="vocab not cached")
    def test_known_gpt2_ids_for_a_known_sentence(self):
        """Pinned against the published GPT-2 vocabulary, not against our own output."""
        import json

        enc = json.loads((MODEL_DIR / "encoder.json").read_text(encoding="utf-8"))
        merges = [tuple(line.split())
                  for line in (MODEL_DIR / "vocab.bpe").read_text(encoding="utf-8").split("\n")[1:]
                  if len(line.split()) == 2]
        ids = Encoder(enc, merges).encode("The quick brown fox jumps over the lazy dog.")
        assert ids[:10] == [464, 2068, 7586, 21831, 18045, 625, 262, 16931, 3290, 13], ids[:10]


class TestEffectSize:
    def test_direction_is_second_minus_first(self):
        assert cohen_d([1.0, 1.1, 0.9], [2.0, 2.1, 1.9]) > 0

    def test_degenerate_arms_do_not_divide_by_zero(self):
        assert cohen_d([1.0], [2.0, 3.0]) is None


class TestContrast:
    def _rows(self, n=60):
        return ([{"text": "x", "g": "a"}] * n) + ([{"text": "x", "g": "b"}] * n)

    def test_missing_values_are_not_a_group(self):
        rows = self._rows() + [{"text": "x", "g": "NA"}] * 60
        out = contrast(rows, lambda t: 1.0, "g", per_group=50)
        assert "NA" not in out["groups"]

    def test_every_result_carries_citation_and_limitation(self):
        out = contrast(self._rows(), lambda t: 1.0, "g", per_group=50)
        assert "not a detector" in out["limitation"].lower()
        assert "gpt-2" in out["citation"].lower()

    def test_sampling_respects_per_group(self):
        out = contrast(self._rows(200), lambda t: 1.0, "g", per_group=40)
        assert all(g["n"] == 40 for g in out["groups"].values())

    def test_a_scorer_that_opts_out_does_not_crash_the_contrast(self):
        out = contrast(self._rows(), lambda t: None, "g", per_group=50)
        assert out["groups"] == {}


@needs_model
class TestAgainstTheRealModel:
    @pytest.fixture(scope="class")
    def scorer(self):
        from eval.gpt2_onnx import Gpt2Perplexity

        return Gpt2Perplexity(MODEL_DIR)

    def test_fluent_prose_beats_the_same_words_shuffled(self, scorer):
        """The probe that holds vocabulary fixed and varies only order.

        A rare-word list is NOT a valid high-perplexity probe -- it is positionally predictable,
        which is exactly how the first version of this test misled me.
        """
        text = ("The committee reviewed the proposal carefully before reaching a decision. "
                "Several members expressed concerns about the timeline, but agreed that the "
                "overall direction was sound and the budget was reasonable given the scope.")
        words = text.split()
        random.Random(0).shuffle(words)
        fluent, shuffled = scorer.nll(text), scorer.nll(" ".join(words))
        assert fluent < shuffled, (
            f"fluent {fluent:.4f} did not score below shuffled {shuffled:.4f}; the sign "
            f"convention is inverted and every published reading flips with it"
        )

    def test_short_text_opts_out(self, scorer):
        assert scorer.nll("too short") is None

    def test_the_token_cap_is_enforced(self, scorer):
        assert scorer.nll(" ".join(["word"] * (MAX_TOKENS * 3))) is not None

    def test_the_minimum_is_where_it_says(self, scorer):
        assert scorer.nll(" ".join(["word"] * (MIN_TOKENS - 5))) is None
