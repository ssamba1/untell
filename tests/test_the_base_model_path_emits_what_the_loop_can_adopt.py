"""The untuned rewriter has to produce candidates the rest of the pipeline can actually accept.

Four separate defects made this path return its input byte-for-byte, and all four printed the same
thing — ``sim 1.000, stopped max_iters``. A document-level prompt that a 1.5B model ignored; whole
document granularity, which made it summarise; ``⟦HZ⟧`` sentinels it could not reproduce, so every
sentence failed integrity; and a per-sentence length band looser than the document's own deletion
allowance, so the assembled candidate was arithmetically certain to be vetoed.

No model is loaded here. ``_generate_once`` is the seam: stub it and the surrounding contract —
which sentences are kept, what is shielded, what the budget permits — is ordinary code.
"""

from __future__ import annotations

import pytest

from untell.rewriter import local_policy as lp
from untell.scripts.preserve import SENTINEL_RE, lock


@pytest.fixture
def rw(monkeypatch):
    r = lp.LocalPolicyRewriter(use_adapter=False)
    monkeypatch.setattr(r, "_load", lambda: None)
    return r


def _fixed(text_map, default=None):
    """A stub generator returning a scripted output per input."""
    def _gen(self, text, *, sentence=False):
        return text_map.get(text.strip(), default if default is not None else text)
    return _gen


class TestSentinelsSurviveTheModel:
    """A sentinel the model drops is a citation the reader loses."""

    def test_shielding_hides_every_sentinel_from_the_model(self):
        masked, mapping = lock("Smith et al. (2020) found 47 cases in version 1.2.3.")
        assert mapping, "the fixture must actually lock something"
        shielded, back = lp._shield_sentinels(masked)
        assert not SENTINEL_RE.findall(shielded)
        assert "[REF0]" in shielded

    def test_a_copied_marker_round_trips_exactly(self):
        masked, _ = lock("Smith et al. (2020) found 47 cases in version 1.2.3.")
        shielded, back = lp._shield_sentinels(masked)
        assert lp._unshield(shielded, back) == masked

    def test_a_dropped_marker_fails_integrity(self):
        masked, _ = lock("Smith et al. (2020) found 47 cases in version 1.2.3.")
        shielded, back = lp._shield_sentinels(masked)
        mangled = lp._unshield(shielded.replace("[REF0]", "one team"), back)
        assert not lp._sentinels_intact(masked, mangled)

    def test_an_invented_marker_is_never_shipped_as_text(self):
        """The model renumbering a marker must not leave `[REF9]` in the reader's document."""
        masked, _ = lock("Smith et al. (2020) found 47 cases.")
        shielded, back = lp._shield_sentinels(masked)
        assert "[REF9]" not in lp._unshield(shielded + " [REF9]", back)

    def test_a_faithful_paraphrase_around_the_markers_keeps_them(self):
        masked, _ = lock("Smith et al. (2020) found 47 cases in version 1.2.3.")
        shielded, back = lp._shield_sentinels(masked)
        assert lp._sentinels_intact(masked, lp._unshield(shielded.replace("found", "reported"), back))


class TestOnlyEverHelpPerSentence:
    def test_an_unfaithful_sentence_reverts_and_costs_the_document_nothing(self, rw, monkeypatch):
        source = "The trial enrolled adults at three separate clinical sites across the region."
        monkeypatch.setattr(rw, "_sentence_is_faithful", lambda *_: False)
        monkeypatch.setattr(
            type(rw), "_generate_once", _fixed({source: "It happened."}), raising=False
        )
        assert rw.rewrite(source, {"max": 0.9}, 0.3) == source

    def test_a_document_whose_sentences_all_revert_comes_back_unchanged(self, rw, monkeypatch):
        text = ("The trial enrolled adults at three separate clinical sites. "
                "The results were published after review by an independent panel.")
        monkeypatch.setattr(rw, "_sentence_is_faithful", lambda *_: False)
        monkeypatch.setattr(type(rw), "_generate_once", _fixed({}, default="x"), raising=False)
        assert rw.rewrite(text, {"max": 0.9}, 0.3) == text

    def test_short_fragments_are_passed_through_untouched(self, rw, monkeypatch):
        """A heading handed to a small model comes back as an invented sentence."""
        called = []

        def _gen(self, text, *, sentence=False):
            called.append(text)
            return "invented prose around the heading"

        monkeypatch.setattr(type(rw), "_generate_once", _gen, raising=False)
        assert rw.rewrite("Methods.", {"max": 0.9}, 0.3) == "Methods."
        assert called == [], "a sub-8-word fragment must never reach the model"


class TestTheDocumentBudget:
    """Sentence-level and document-level faithfulness are different constraints."""

    def test_compression_stops_once_the_document_allowance_is_spent(self, rw, monkeypatch):
        # Ten sentences of ten words. `deletion_allowance` permits max(10, 10%) = 10 words.
        sentence = "alpha beta gamma delta epsilon zeta eta theta iota kappa."
        text = " ".join([sentence] * 10)
        # Each rewrite is faithful by the guard but drops three words.
        monkeypatch.setattr(rw, "_sentence_is_faithful", lambda *_: True)
        monkeypatch.setattr(
            type(rw), "_generate_once",
            _fixed({}, default="alpha beta gamma delta epsilon zeta eta."), raising=False
        )
        out = rw.rewrite(text, {"max": 0.9}, 0.3)
        lost = len(text.split()) - len(out.split())
        allowance = 10
        assert lost <= allowance, f"spent {lost} words against an allowance of {allowance}"
        assert out != text, "the budget must permit some rewriting, not block all of it"

    def test_a_rewrite_that_does_not_shrink_is_never_budget_limited(self, rw, monkeypatch):
        sentence = "alpha beta gamma delta epsilon zeta eta theta iota kappa."
        text = " ".join([sentence] * 10)
        monkeypatch.setattr(rw, "_sentence_is_faithful", lambda *_: True)
        monkeypatch.setattr(
            type(rw), "_generate_once",
            _fixed({}, default="alpha beta gamma delta epsilon zeta eta theta iota lambda."),
            raising=False,
        )
        out = rw.rewrite(text, {"max": 0.9}, 0.3)
        assert out.count("lambda") == 10, "equal-length rewrites must all be adopted"


class TestTheTrainedPolicyIsUntouched:
    """Every change here is scoped to the untuned path; the adapter was RL-trained on one prompt."""

    def test_the_adapter_path_rewrites_the_whole_document_in_one_pass(self, monkeypatch):
        r = lp.LocalPolicyRewriter(adapter_dir="anything", use_adapter=True)
        monkeypatch.setattr(r, "_load", lambda: None)
        seen = []

        def _gen(self, text, *, sentence=False):
            seen.append((text, sentence))
            return "rewritten"

        monkeypatch.setattr(type(r), "_generate_once", _gen, raising=False)
        text = "First sentence with enough words to matter here. Second sentence, also long enough."
        assert r.rewrite(text, {"max": 0.9}, 0.3) == "rewritten"
        assert seen == [(text, False)], "the adapter must see the whole document, once"

    def test_the_base_path_can_be_forced_back_to_one_pass_for_the_ab(self, monkeypatch):
        r = lp.LocalPolicyRewriter(use_adapter=False)
        monkeypatch.setattr(r, "_load", lambda: None)
        monkeypatch.setenv("UNTELL_POLICY_WHOLE_DOC", "1")
        seen = []

        def _gen(self, text, *, sentence=False):
            seen.append(sentence)
            return "rewritten"

        monkeypatch.setattr(type(r), "_generate_once", _gen, raising=False)
        text = "First sentence with enough words to matter here. Second sentence, also long enough."
        r.rewrite(text, {"max": 0.9}, 0.3)
        assert seen == [False]


class TestPreambleStripping:
    @pytest.mark.parametrize("raw,want", [
        ("Here is the rewritten text:\nReal content follows.", "Real content follows."),
        ("```\nFenced body text.\n```", "Fenced body text."),
        ('"Wrapped in quotes."', "Wrapped in quotes."),
    ])
    def test_announcing_wrappers_are_removed(self, raw, want):
        assert lp._strip_preamble(raw) == want

    @pytest.mark.parametrize("raw", [
        "The study found three things. It also noted a caveat.",
        "The committee reached the following conclusions after reviewing every dataset at length:\nOne.",
    ])
    def test_real_content_is_never_removed(self, raw):
        """A caveat that eats prose is worse than no caveat."""
        assert lp._strip_preamble(raw) == raw
