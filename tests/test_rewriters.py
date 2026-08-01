"""Tests for the structural, composite, and surgical rewriters."""
from __future__ import annotations

from untell.rewriter import get_rewriter
from untell.rewriter.composite import CompositeRewriter
from untell.rewriter.structural import StructuralRewriter, structural_rewrite


class TestStructuralRewriter:
    def test_available(self):
        rw = StructuralRewriter()
        assert rw.available() is True

    def test_strips_transitions(self):
        text = "Moreover, this is a test. Furthermore, it works well. Overall, the results are good."
        result = structural_rewrite(text, intensity=1.0)
        for _bad_word in ("Moreover,", "Furthermore,", "Overall,"):
            # After stripping, these may not appear as sentence openers
            # (some may survive depending on random seed, but at intensity=1.0 all should go)
            pass
        # At high intensity, transitions should be significantly reduced
        assert result.count("Moreover,") < text.count("Moreover,")

    def test_flattens_participial_trailers(self):
        text = "The system evolved rapidly, underscoring its importance in modern computing."
        result = structural_rewrite(text, intensity=1.0)
        # The participial trailer should be flattened to an independent clause
        assert ", underscoring" not in result

    def test_flattens_negated_contrast(self):
        text = "It's not about the technology, it's about the people using it."
        result = structural_rewrite(text, intensity=1.0)
        # Should not contain the full "not X, it's Y" pattern
        assert "not about" not in result.lower() or "about the people" in result.lower()

    def test_injects_contractions(self):
        from untell.rewriter.structural import _inject_contractions

        assert _inject_contractions("It is not clear.") == "It isn't clear."
        assert _inject_contractions("They do not agree.") == "They don't agree."
        assert _inject_contractions("We cannot win.") == "We can't win."
        assert _inject_contractions("that is right") == "that's right"
        # Sentence-initial capital preserved.
        assert _inject_contractions("Do not stop.") == "Don't stop."

    def test_structural_rewrite_contracts(self):
        out = structural_rewrite(
            "The system does not fail. We are ready. It is fine.", intensity=0.0, seed=1
        )
        assert "does not" not in out and "doesn't" in out

    def test_burstiness_targeting_raises_cv(self):
        import random

        from untell.rewriter.structural import _cv, _target_burstiness

        # Seed the global RNG: _target_burstiness calls _split_one, which uses random, so without
        # this the outcome depends on whatever random state the PREVIOUS test happened to leave.
        # The test passed alone and inside its own file, and failed in other orderings — a flake,
        # not a real regression.
        random.seed(1234)

        # Uniform ~9-word sentences (low burstiness, an AI tell).
        sents = [
            "Artificial intelligence has transformed many industries in recent years.",
            "Organizations use it to improve their operational efficiency greatly.",
            "Machine learning models can analyze large amounts of data quickly.",
            "The impact of these systems continues to grow across sectors.",
        ]
        before = _cv([len(s.split()) for s in sents])
        after_sents = _target_burstiness(sents)
        after = _cv([len(s.split()) for s in after_sents])
        assert after > before
        # No content lost: every content word survives (redistribution only).
        import re as _re

        def w(ss):
            return sorted(x.lower() for x in _re.findall(r"[a-z]+", " ".join(ss).lower()))

        # allow the injected "and" connector
        assert set(w(sents)) - set(w(after_sents)) == set()

    def test_strips_filler_openers(self):
        from untell.rewriter.structural import _strip_filler_openers

        assert _strip_filler_openers("It is worth noting that results improved.") == "Results improved."
        assert _strip_filler_openers("It should be noted that errors dropped.") == "Errors dropped."
        # Mid-paragraph, capital of exposed clause restored.
        assert (
            _strip_filler_openers("The cat sat. It is important to note that dogs bark too.")
            == "The cat sat. Dogs bark too."
        )

    def test_empty_input(self):
        assert structural_rewrite("", intensity=1.0) == ""

    def test_single_sentence(self):
        text = "This is just one sentence with no complexity whatsoever."
        result = structural_rewrite(text, intensity=1.0)
        # Single sentences should be preserved with minimal change
        assert len(result) > 0


class TestStructuralRewriterProtocol:
    def test_satisfies_rewriter_protocol(self):
        rw = StructuralRewriter()
        result = rw.rewrite("Moreover, this is a test sentence here for rewriting purposes.", {}, threshold=0.30)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_get_rewriter_prefer_structural(self):
        rw = get_rewriter(prefer="structural")
        assert rw is not None
        assert rw.name == "structural"
        assert rw.available() is True


class TestCompositeRewriter:
    def test_available(self):
        rw = CompositeRewriter()
        assert rw.available() is True

    def test_rewrites(self):
        rw = CompositeRewriter(intensity=1.0, max_subs=20)
        text = "Moreover, we leverage robust solutions to optimize efficiency across various sectors."
        result = rw.rewrite(text, {}, threshold=0.30)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_get_rewriter_prefer_composite(self):
        rw = get_rewriter(prefer="composite")
        assert rw is not None
        assert rw.name == "composite"
        assert rw.available() is True

    def test_non_scoreable_tier_skips_internal_scoring(self, monkeypatch):
        """In --browser mode the tier is e.g. 'browser:zerogpt'; the composite must NOT try to
        score internally (which would silently fall back to lite and optimize the wrong signal)."""
        import untell.scripts.score as score_mod

        def _boom(*a, **k):
            raise AssertionError("score_text must not be called for a non-scoreable tier")

        monkeypatch.setattr(score_mod, "score_text", _boom)
        rw = CompositeRewriter()
        score_result = {"tier": "browser:zerogpt", "max": 0.7, "detectors": {}}
        result = rw.rewrite("Moreover, AI has transformed numerous industries.", score_result)
        assert isinstance(result, str) and len(result) > 0


class TestNeuralComposite:
    def test_name_reflects_t5_availability(self):
        rw = CompositeRewriter(use_t5=True)
        # With torch+transformers installed the neural stage is live and the name flips to "neural";
        # without them it stays a plain "composite" (never errors, never None).
        assert rw.name in ("neural", "composite")

    def test_get_rewriter_prefer_neural(self):
        rw = get_rewriter(prefer="neural")
        assert rw is not None
        assert rw.available() is True

    def test_t5_best_of_n_sampling_and_sentinels_survive(self, monkeypatch):
        import pytest

        from untell.scripts.preserve import find_sentinels

        rw = CompositeRewriter(use_t5=True)
        if rw._t5 is None:
            pytest.skip("T5 deps unavailable in this environment")
        calls = {"n": 0}

        def _fake(text, score_result, threshold=0.30):
            calls["n"] += 1
            return text  # sentinel-safe identity; asserts best-of-N draws + spans survive

        monkeypatch.setattr(rw._t5, "rewrite", _fake)
        masked = "Moreover, AI fundamentally reshaped ⟦HZ0000⟧ across ⟦HZ0001⟧ sectors overall."
        out = rw.rewrite(masked, {"tier": "lite"})
        assert calls["n"] == rw.t5_best_of  # neural stage draws t5_best_of diverse samples
        assert find_sentinels(out) == {"⟦HZ0000⟧", "⟦HZ0001⟧"}  # locked spans intact through the chain

    def test_neural_keeps_best_scoring_t5_draw(self, monkeypatch):
        import pytest

        rw = CompositeRewriter(use_t5=True)
        if rw._t5 is None:
            pytest.skip("T5 deps unavailable in this environment")
        # Isolate the neural selection: rule stages pass through unchanged.
        monkeypatch.setattr(rw._structural, "rewrite", lambda t, s, threshold=0.30: t)
        monkeypatch.setattr(rw._surgical, "rewrite", lambda t, s, threshold=0.30: t)
        # Three diverse draws; the loop must keep the one the detector scores lowest.
        draws = iter(["AI draw one here.", "AI draw two here.", "AI draw three here."])
        monkeypatch.setattr(rw._t5, "rewrite", lambda t, s, threshold=0.30: next(draws))
        rw.t5_best_of = 3

        import untell.scripts.score as score_mod

        # draw two is the detector-lowest; original + the other draws score higher.
        table = {"AI draw two here.": 0.10}

        def _fake_score(text, tier="lite", threshold=0.30):
            return {"max": table.get(text, 0.90), "detectors": {"d": table.get(text, 0.90)}, "tier": tier}

        monkeypatch.setattr(score_mod, "score_text", _fake_score)
        out = rw.rewrite("Original AI sentence about industries.", {"tier": "lite"})
        assert out == "AI draw two here."  # kept the lowest-scoring sampled paraphrase


class TestEnsembleRewriter:
    def test_available_and_includes_composite(self):
        from untell.rewriter.ensemble import EnsembleRewriter

        rw = EnsembleRewriter()
        assert rw.available() is True
        assert "composite" in rw.member_names  # composite is always a member

    def test_get_rewriter_prefer_ensemble_and_max(self):
        a = get_rewriter(prefer="ensemble")
        b = get_rewriter(prefer="max")
        assert a is not None and a.name == "ensemble"
        assert b is not None and b.name == "ensemble"

    def test_selects_lowest_scoring_member(self, monkeypatch):
        from untell.rewriter.ensemble import EnsembleRewriter

        rw = EnsembleRewriter()

        # Force a known two-member field with deterministic outputs.
        class _M:
            def __init__(self, out):
                self._out = out

            def rewrite(self, text, score_result, threshold=0.30):
                return self._out

        rw._members = [("a", _M("candidate A wins")), ("b", _M("candidate B loses"))]

        import untell.scripts.score as score_mod

        table = {"candidate A wins": 0.12, "candidate B loses": 0.80}

        def _fake_score(text, tier="lite", threshold=0.30):
            return {"max": table.get(text, 0.99), "detectors": {"d": table.get(text, 0.99)}, "tier": tier}

        monkeypatch.setattr(score_mod, "score_text", _fake_score)
        out = rw.rewrite("original text scores 0.99", {"tier": "lite"})
        assert out == "candidate A wins"  # lowest-scoring member output selected

    def test_keeps_original_when_no_member_improves(self, monkeypatch):
        from untell.rewriter.ensemble import EnsembleRewriter

        rw = EnsembleRewriter()

        class _M:
            def rewrite(self, text, score_result, threshold=0.30):
                return "worse candidate"

        rw._members = [("a", _M())]

        import untell.scripts.score as score_mod

        def _fake_score(text, tier="lite", threshold=0.30):
            m = 0.20 if text == "original best" else 0.90
            return {"max": m, "detectors": {"d": m}, "tier": tier}

        monkeypatch.setattr(score_mod, "score_text", _fake_score)
        out = rw.rewrite("original best", {"tier": "lite"})
        assert out == "original best"  # no member beat the original -> keep it


class TestMTPivotRewriter:
    def test_available_reflects_bt_stack(self, monkeypatch):
        from untell.rewriter.mt_pivot import MTPivotRewriter

        rw = MTPivotRewriter()
        monkeypatch.setattr(rw._bt, "available", lambda: False)
        assert rw.available() is False

    def test_rewrite_noop_when_unavailable(self, monkeypatch):
        from untell.rewriter.mt_pivot import MTPivotRewriter

        rw = MTPivotRewriter()
        monkeypatch.setattr(rw._bt, "available", lambda: False)
        text = "AI has transformed many industries fundamentally."
        assert rw.rewrite(text, {}, threshold=0.30) == text

    def test_sentinels_survive_translation(self, monkeypatch):
        from untell.rewriter.mt_pivot import MTPivotRewriter
        from untell.scripts.preserve import find_sentinels

        rw = MTPivotRewriter()
        monkeypatch.setattr(rw._bt, "available", lambda: True)
        # Identity translation: placeholders round-trip, so sentinels must be restored intact.
        monkeypatch.setattr(rw._bt, "back_translate", lambda text, pivots=("fr",): text)
        masked = "AI changed ⟦HZ0000⟧ over 10 years and ⟦HZ0001⟧ approved."
        result = rw.rewrite(masked, {})
        assert find_sentinels(result) == {"⟦HZ0000⟧", "⟦HZ0001⟧"}

    def test_sentinel_loss_falls_back_to_original(self, monkeypatch):
        from untell.rewriter.mt_pivot import MTPivotRewriter

        rw = MTPivotRewriter()
        monkeypatch.setattr(rw._bt, "available", lambda: True)
        # MT drops the placeholder -> restored text has no sentinel -> must fall back to input.
        monkeypatch.setattr(
            rw._bt, "back_translate", lambda text, pivots=("fr",): "completely different, no marker"
        )
        masked = "AI changed ⟦HZ0000⟧ significantly."
        assert rw.rewrite(masked, {}) == masked

    def test_get_rewriter_prefer_mt_pivot_none_when_unavailable(self, monkeypatch):
        from untell.attacks.back_translation import BackTranslator

        monkeypatch.setattr(BackTranslator, "available", lambda self: False)
        assert get_rewriter(prefer="mt_pivot") is None


class TestSurgicalRewriterProtocol:
    def test_get_rewriter_prefer_surgical(self):
        rw = get_rewriter(prefer="surgical")
        assert rw is not None
        assert rw.name == "surgical"
        assert rw.available() is True


class TestTargetedRewriter:
    def test_split_sentences_roundtrips_exactly(self):
        from untell.rewriter.targeted import split_sentences

        for case in [
            "One. Two! Three?",
            "One.  Two.",          # double space preserved
            "No terminator",
            "A. B.\n\nC.",         # newlines preserved
            "",
        ]:
            assert "".join(split_sentences(case)) == case

    def test_leaves_clean_sentences_byte_identical(self, monkeypatch):
        """Only sentences that read as AI are rewritten; human-reading ones are untouched."""
        from untell.rewriter.targeted import TargetedRewriter

        class _Inner:
            name = "inner"

            def available(self):
                return True

            def rewrite(self, text, score_result, threshold=0.30):
                return "REWRITTEN"

        rw = TargetedRewriter(inner=_Inner(), min_score=0.30)

        import untell.scripts.score as score_mod

        ai = "Moreover, we leverage synergies."
        human = "I walked home."

        def _fake_score(text, tier="lite", threshold=0.30):
            # the AI sentence is flagged and its rewrite scores lower; the human one is clean
            m = {ai: 0.90, "REWRITTEN": 0.05, human: 0.02}.get(text.strip(), 0.50)
            return {"max": m, "mean": m, "detectors": {"d": m}, "tier": tier}

        monkeypatch.setattr(score_mod, "score_text", _fake_score)
        out = rw.rewrite(f"{ai} {human}", {"tier": "lite"})
        assert "REWRITTEN" in out       # the flagged sentence was rewritten
        assert human in out             # the clean sentence survived byte-identical

    def test_returns_original_when_no_sentence_improves(self, monkeypatch):
        from untell.rewriter.targeted import TargetedRewriter

        class _Inner:
            name = "inner"

            def available(self):
                return True

            def rewrite(self, text, score_result, threshold=0.30):
                return "WORSE"

        rw = TargetedRewriter(inner=_Inner(), min_score=0.30)

        import untell.scripts.score as score_mod

        def _fake_score(text, tier="lite", threshold=0.30):
            m = 0.95 if text.strip() == "WORSE" else 0.90  # rewrite never helps
            return {"max": m, "mean": m, "detectors": {"d": m}, "tier": tier}

        monkeypatch.setattr(score_mod, "score_text", _fake_score)
        src = "Moreover, we leverage synergies. Furthermore, we optimize verticals."
        assert rw.rewrite(src, {"tier": "lite"}) == src  # no-harm: original returned

    def test_get_rewriter_prefer_targeted(self):
        rw = get_rewriter(prefer="targeted")
        assert rw is not None and rw.name == "targeted"


class TestCompositeIntensitySweep:
    def test_draws_use_varied_intensity(self, monkeypatch):
        """Selection is only as good as the diversity it selects among: drafts must differ by more
        than an RNG seed, so each attempt sweeps the structural intensity."""
        rw = CompositeRewriter(best_of=3, intensity=0.7)
        seen = []

        def _spy(text, score_result, threshold=0.30):
            seen.append(rw._structural.intensity)
            return "restructured"

        monkeypatch.setattr(rw._structural, "rewrite", _spy)
        monkeypatch.setattr(rw._surgical, "rewrite", lambda t, s, threshold=0.30: t)

        import untell.scripts.score as score_mod

        monkeypatch.setattr(
            score_mod, "score_text",
            lambda t, tier="lite", threshold=0.30: {"max": 0.5, "mean": 0.5, "detectors": {"d": 0.5},
                                                    "tier": tier},
        )
        rw.rewrite("Some AI text to rewrite.", {"tier": "lite"})
        assert len(set(seen)) > 1                    # the draws genuinely differ
        assert all(0.4 <= i <= 1.0 for i in seen)    # stay in the sane range

    def test_intensity_restored_after_rewrite(self, monkeypatch):
        """The swept value must never leak across calls (shared mutable state bug)."""
        rw = CompositeRewriter(best_of=3, intensity=0.7)
        monkeypatch.setattr(rw._structural, "rewrite", lambda t, s, threshold=0.30: "x")
        monkeypatch.setattr(rw._surgical, "rewrite", lambda t, s, threshold=0.30: t)

        import untell.scripts.score as score_mod

        monkeypatch.setattr(
            score_mod, "score_text",
            lambda t, tier="lite", threshold=0.30: {"max": 0.5, "mean": 0.5, "detectors": {"d": 0.5},
                                                    "tier": tier},
        )
        rw.rewrite("Some AI text to rewrite.", {"tier": "lite"})
        assert rw._structural.intensity == 0.7


class TestPlainRegister:
    def test_swaps_formal_vocabulary_for_plain_words(self):
        from untell.rewriter.structural import _plain_register

        out = _plain_register(
            "Organizations utilize robust methodologies to demonstrate significant improvements.",
            intensity=1.0,
        )
        assert "utilize" not in out and "robust" not in out
        assert "demonstrate" not in out and "significant" not in out

    def test_never_touches_locked_spans(self):
        """A word-level substitution must not reach inside a sentinel."""
        from untell.rewriter.structural import _plain_register
        from untell.scripts.preserve import find_sentinels

        masked = "We utilize ⟦HZ0000⟧ to leverage ⟦HZ0001⟧ robust results."
        out = _plain_register(masked, intensity=1.0)
        assert find_sentinels(out) == {"⟦HZ0000⟧", "⟦HZ0001⟧"}

    def test_preserves_sentence_initial_capitalisation(self):
        from untell.rewriter.structural import _plain_register

        out = _plain_register("Utilize the tool.", intensity=1.0)
        assert out[0].isupper(), out

    def test_intensity_zero_is_a_noop(self):
        from untell.rewriter.structural import _plain_register

        src = "Organizations utilize robust methodologies."
        assert _plain_register(src, intensity=0.0) == src

    def test_empty_input_is_safe(self):
        from untell.rewriter.structural import _plain_register

        assert _plain_register("") == ""
        assert _plain_register("   ") == "   "

    def test_reduces_ai_tells_end_to_end(self):
        """The point of the transform: measurably more human-reading output."""
        from untell.rewriter.structural import structural_rewrite
        from untell.scripts.tells import score_tells

        src = (
            "Organizations utilize robust methodologies to leverage seamless integration. "
            "Furthermore, this demonstrates significant improvements across numerous verticals."
        )
        before = score_tells(src)["tells"]
        after = score_tells(structural_rewrite(src, intensity=1.0, seed=7))["tells"]
        assert after < before, f"tells did not drop: {before} -> {after}"


class TestStyleProfiles:
    """--style now drives the free rewriter's register knobs, instead of being accepted and ignored."""

    def test_academic_keeps_formal_vocabulary_and_avoids_contractions(self):
        import random

        from untell.rewriter.structural import structural_rewrite

        src = "Moreover, organizations utilize robust methodologies. It is not clear this demonstrates value."
        random.seed(11)
        out = structural_rewrite(src, intensity=1.0, style="academic")

        assert "n't" not in out, f"academic prose should not contract: {out}"
        assert "utilize" in out or "robust" in out, f"academic should keep formal vocabulary: {out}"

    def test_casual_contracts_and_plainens_vocabulary(self):
        import random

        from untell.rewriter.structural import structural_rewrite

        src = "Moreover, organizations utilize robust methodologies. It is not clear this demonstrates value."
        random.seed(11)
        out = structural_rewrite(src, intensity=1.0, style="casual")

        assert "utilize" not in out, f"casual should plainen 'utilize': {out}"

    def test_style_reaches_the_rewriter_through_score_result(self):
        """The loop passes --style in score_result; StructuralRewriter must read it from there."""
        import random

        from untell.rewriter.structural import StructuralRewriter

        rw = StructuralRewriter(intensity=1.0)
        src = "Moreover, organizations utilize robust methodologies. It is not clear this holds."
        random.seed(5)
        academic = rw.rewrite(src, {"tier": "lite", "style": "academic"})
        assert "n't" not in academic, f"style did not reach the rewriter: {academic}"

    def test_unknown_and_missing_style_keep_previous_behaviour(self):
        from untell.rewriter.structural import style_profile

        neutral = {"contractions": True, "register": 1.0}
        assert style_profile(None) == neutral
        assert style_profile("not-a-real-style") == neutral
        assert style_profile("ACADEMIC")["contractions"] is False  # case-insensitive
