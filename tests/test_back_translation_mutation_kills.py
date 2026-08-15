"""Killing tests for mutation survivors in `untell/attacks/back_translation.py`.

The module's model calls are all behind `BackTranslator._pipe`, so every test here stubs
that seam with a fake tokenizer/model that counts words like MarianMT's SentencePiece
vocabulary but needs no network and no 5 GB download. The real `_chunk`/`_fit`/`_translate`
code runs in full; only the model objects are fakes. The recording fakes also pin the
call-site contract (`truncation=True`, `padding=True`, `num_beams=4`,
`skip_special_tokens=True`) — the guarantees the module's own docstrings make about not
silently discarding text.

Mutation names match `python .claude/mutate.py untell/attacks/back_translation.py --list`.
"""

from __future__ import annotations

import pytest

from untell.attacks.back_translation import BackTranslator


class _FakeTok:
    """One token per word — small, and exact at the boundaries the tests measure."""

    def __init__(self) -> None:
        self.call_kwargs: list[dict] = []
        self.decode_kwargs: list[dict] = []

    def __call__(self, text, **kwargs):
        self.call_kwargs.append(kwargs)
        if isinstance(text, list):
            n = max(len(x.split()) for x in text) if text else 0
            return {"input_ids": [[0] * n for _ in text]}
        return {"input_ids": [0] * len(text.split())}

    def batch_decode(self, gen, **kwargs):
        self.decode_kwargs.append(kwargs)
        return ["fake-translation"]


class _FakeModel:
    def __init__(self) -> None:
        self.generate_kwargs: dict | None = None

    def generate(self, **kwargs):
        self.generate_kwargs = kwargs
        return [[0, 1, 2]]


BUDGET = BackTranslator()._MAX_TOKENS - 16  # 496


def _bt_with_fakes():
    bt = BackTranslator()
    tok = _FakeTok()
    model = _FakeModel()
    bt._pipe = lambda src, tgt: (tok, model)
    return bt, tok, model


class TestAvailability:
    """`available()` and the empty-input guard (lines 35-36, 136)."""

    def test_back_translate_runs_the_round_trip(self, monkeypatch):
        # back_translation.py:35  constant: False -> True   (import-failure branch)
        # back_translation.py:36  constant: True -> False   (success branch)
        # The dependencies are importable here, so `available()` is True and the round
        # trip must actually happen; either mutation makes `back_translate` no-op.
        bt, tok, _ = _bt_with_fakes()
        assert bt.back_translate("Hello world") == "fake-translation"

    def test_back_translate_returns_whitespace_input_unchanged(self, monkeypatch):
        # back_translation.py:136  logic: or -> and   (`not text.strip() or not available()`)
        # Whitespace-only input must short-circuit on the first clause; the mutated
        # `and` needs both to be true and sends "   " through the translator.
        bt, tok, _ = _bt_with_fakes()
        assert bt.back_translate("   ") == "   "


class TestPipeCache:
    """`_pipe` cache hit path (line 40)."""

    def test_pipe_uses_the_cache_when_present(self, monkeypatch):
        # back_translation.py:40  membership: not in -> in
        # With the pair already cached, `_pipe` must return it without touching
        # transformers. The mutated membership enters the load branch and calls
        # from_pretrained, which is stubbed to raise — and back_translate then falls
        # back to the no-op, losing the translation.
        import transformers

        def boom(*a, **k):
            raise AssertionError("from_pretrained must not be called on a cache hit")

        monkeypatch.setattr(transformers.MarianTokenizer, "from_pretrained", boom)
        monkeypatch.setattr(transformers.MarianMTModel, "from_pretrained", boom)
        bt, tok, _ = _bt_with_fakes()
        BackTranslator._cache[("en", "fr")] = (tok, _FakeModel())
        try:
            assert bt.back_translate("Hello world") == "fake-translation"
        finally:
            BackTranslator._cache.clear()


class TestChunking:
    """`_chunk` token-budget logic (lines 50, 67, 79, 86)."""

    def test_chunk_splits_a_sentence_over_the_token_budget(self):
        # back_translation.py:50  constant: 512 -> 513   (_MAX_TOKENS)
        # A 497-word sentence is one token over the real budget (512 - 16 = 496); the
        # bumped cap lets it through whole and the caller would truncate it silently.
        assert len(BackTranslator()._chunk(" ".join(["w"] * 497), _FakeTok())) == 2

    def test_chunk_keeps_a_sentence_at_the_budget_in_one_piece(self):
        # back_translation.py:67  constant: 16 -> 17   (budget = _MAX_TOKENS - 16)
        # 496 words exactly fill the budget; the shrunken budget splits them.
        assert len(BackTranslator()._chunk(" ".join(["w"] * 496), _FakeTok())) == 1

    def test_chunk_merges_sentences_that_exactly_fill_the_budget(self):
        # back_translation.py:79  boundary: > -> >=   (size test in the pack loop)
        # 200 + 296 words is exactly 496: the merged candidate fits, and the mutated
        # `>=` would flush the first sentence into its own chunk for no reason.
        # ("zz" not "w": a single-letter word + period reads as an initial, which
        # split_sentences treats as an abbreviation and refuses to split on.)
        text = " ".join(["zz"] * 199) + " zz. " + " ".join(["zz"] * 296)
        assert len(BackTranslator()._chunk(text, _FakeTok())) == 1

    def test_chunk_of_whitespace_returns_the_input(self):
        # back_translation.py:86  logic: or -> and   (`return chunks or [text]`)
        # No sentences, no chunks: the fallback must be the input itself, not [].
        assert BackTranslator()._chunk("   ", _FakeTok()) == ["   "]


class TestFit:
    """`_fit` clause- and word-level splitting (lines 96, 104, 115, 119)."""

    def test_fit_leaves_a_sentence_at_exactly_the_budget_whole(self):
        # back_translation.py:96  boundary: <= -> <   (early return on a fitting sentence)
        # A sentence of exactly 496 words must short-circuit whole. The clause boundary
        # carries a two-space run: the mutated `<` falls through, `_CLAUSE.split`
        # consumes the run, and the greedy re-merge normalises it to one space — so the
        # returned piece differs from the sentence that was handed in.
        text = " ".join(["zz"] * 400) + " zz,  " + " ".join(["zz"] * 95)
        assert BackTranslator()._fit(text, _FakeTok(), BUDGET) == [text]

    def test_fit_merges_clauses_that_exactly_fill_the_budget(self):
        # back_translation.py:104  boundary: > -> >=   (size test in the greedy pack)
        # A 485-word clause plus a 10-word clause is exactly 496: they must pack into
        # one piece, not be flushed apart by the mutated `>=`.
        text = " ".join(["w"] * 485) + ", " + " ".join(["w"] * 10)
        assert len(BackTranslator()._fit(text, _FakeTok(), BUDGET)) == 1

    def test_fit_never_emits_an_empty_piece_from_an_oversized_clause(self):
        # back_translation.py:104  logic: and -> or   (`if cur and len(tok(candidate)) ...`)
        # With a 600-word clause the greedy pack starts with an empty buffer; the
        # mutated `or` runs the size test anyway and appends "" before the clause.
        text = " ".join(["w"] * 600) + ", " + " ".join(["w"] * 10)
        pieces = BackTranslator()._fit(text, _FakeTok(), BUDGET)
        assert "" not in pieces

    def test_fit_keeps_a_clause_at_exactly_the_budget_verbatim(self):
        # back_translation.py:115  boundary: <= -> <   (clause size test)
        # A 496-word clause with double spaces sits exactly on the budget; the mutated
        # `<` re-splits it by words, which rejoins with single spaces and rewrites the
        # clause the translator would receive.
        text = "w  " * 495 + "w, w"
        pieces = BackTranslator()._fit(text, _FakeTok(), BUDGET)
        assert "  " in pieces[0]

    def test_fit_splits_an_oversized_sentence_into_pieces(self):
        # back_translation.py:119  logic: or -> and   (`return pieces or [sentence]`)
        # With real pieces produced, the mutated `and` discards them and returns the
        # whole oversized sentence — the exact silent-truncation shape this code exists
        # to prevent.
        assert len(BackTranslator()._fit(" ".join(["w"] * 600), _FakeTok(), BUDGET)) == 2


class TestTranslateCallContract:
    """`_translate` model call site (lines 127-131).

    The fakes record what `_translate` actually asks the tokenizer and model to do, so
    these tests pin the contract the module's docstrings promise: truncation at the
    model's own cap (never silent drops below it), padding, 4-beam generation, and
    decoding without special tokens.
    """

    def _translate_once(self):
        bt, tok, model = _bt_with_fakes()
        out = bt._translate("Hello world", "en", "fr")
        return out, tok, model

    def test_translate_requests_truncation_at_the_models_cap(self):
        # back_translation.py:127  constant: True -> False   (truncation=True)
        out, tok, model = self._translate_once()
        assert out == "fake-translation"
        assert tok.call_kwargs[-1]["truncation"] is True

    def test_translate_requests_padding(self):
        # back_translation.py:128  constant: True -> False   (padding=True)
        _, tok, _ = self._translate_once()
        assert tok.call_kwargs[-1]["padding"] is True

    def test_translate_generates_with_four_beams(self):
        # back_translation.py:130  constant: 4 -> 5   (num_beams=4)
        _, _, model = self._translate_once()
        assert model.generate_kwargs["num_beams"] == 4

    def test_translate_decodes_skipping_special_tokens(self):
        # back_translation.py:131  constant: True -> False   (skip_special_tokens=True)
        _, tok, _ = self._translate_once()
        assert tok.decode_kwargs[-1]["skip_special_tokens"] is True
