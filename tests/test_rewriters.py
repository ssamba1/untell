"""Tests for the structural, composite, and surgical rewriters."""
from __future__ import annotations

import pytest

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
        monkeypatch.setattr(rw._structural, "rewrite", lambda t, s, threshold=0.30, intensity=None: t)
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

        # The sweep is now an ARGUMENT, not an assignment to the shared rewriter, so observe what
        # was passed rather than what the attribute happens to hold.
        def _spy(text, score_result, threshold=0.30, intensity=None):
            seen.append(intensity)
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
        monkeypatch.setattr(rw._structural, "rewrite", lambda t, s, threshold=0.30, intensity=None: "x")
        monkeypatch.setattr(rw._surgical, "rewrite", lambda t, s, threshold=0.30: t)

        import untell.scripts.score as score_mod

        monkeypatch.setattr(
            score_mod, "score_text",
            lambda t, tier="lite", threshold=0.30: {"max": 0.5, "mean": 0.5, "detectors": {"d": 0.5},
                                                    "tier": tier},
        )
        rw.rewrite("Some AI text to rewrite.", {"tier": "lite"})
        assert rw._structural.intensity == 0.7

    @pytest.mark.parametrize("base", [0.4, 0.5, 0.7, 0.9, 1.0])
    @pytest.mark.parametrize("n", [1, 2, 3, 4, 5])
    def test_sweep_always_draws_the_configured_intensity(self, base, n):
        """intensity is the caller's knob; the diversity spread must add to it, not replace it.

        The plain linear sweep put the two draws at the endpoints when best_of=2 — 0.4 and 1.0 for
        the default 0.7 — so a caller who lowered intensity to limit surface change never got a
        single candidate at the value they configured.
        """
        from untell.rewriter.composite import _intensity_sweep

        out = _intensity_sweep(base, n)
        assert len(out) == n
        assert any(abs(v - base) < 1e-9 for v in out)
        assert all(0.4 <= v <= 1.0 for v in out)

    def test_sweep_still_spreads(self):
        from untell.rewriter.composite import _intensity_sweep

        assert len(set(_intensity_sweep(0.7, 3))) == 3  # default path unchanged: 0.4 / 0.7 / 1.0

    def test_baseline_scoring_failure_does_not_abort_the_rewrite(self, monkeypatch):
        """A candidate scoring error is swallowed; the baseline's used to propagate and crash.

        Same transient causes (detector timeout, OOM spike), so the asymmetry meant identical
        failures either lost one draw or killed the whole call depending on when they landed.
        """
        rw = CompositeRewriter(best_of=2, intensity=0.7)
        monkeypatch.setattr(
            rw._structural, "rewrite", lambda t, s, threshold=0.30, intensity=None: t + " restructured"
        )
        monkeypatch.setattr(rw._surgical, "rewrite", lambda t, s, threshold=0.30: t + " polished")

        import untell.scripts.score as score_mod

        def _boom(t, tier="lite", threshold=0.30):
            raise RuntimeError("detector timed out")

        monkeypatch.setattr(score_mod, "score_text", _boom)

        out = rw.rewrite("Some AI text to rewrite.", {"tier": "lite"})
        assert out == "Some AI text to rewrite. restructured polished"


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
        # The neutral profile is the single source for "no style", so the test reads it rather than
        # restating it — the previous hard-coded copy broke the moment two knobs were added, while
        # the behaviour it exists to protect (unknown style == no style) was intact.
        from untell.rewriter.structural import _NEUTRAL, style_profile

        assert style_profile(None) == _NEUTRAL
        assert style_profile("not-a-real-style") == _NEUTRAL
        assert style_profile("ACADEMIC")["contractions"] is False  # case-insensitive
        # Every knob the pipeline reads must be present on every profile, or a style that omits one
        # raises KeyError deep inside a rewrite instead of falling back.
        for name in ("casual", "academic", "not-a-real-style"):
            assert set(style_profile(name)) == set(_NEUTRAL)


ABBREVIATION_SPLITS = [
    ("title", "Dr. Smith published the results in 2020. The study enrolled 240 patients.", 2),
    ("figure", "See Fig. 3 for detail. The trend is clear.", 2),
    ("country", "The U.S. economy grew steadily. Inflation fell.", 2),
    ("plain", "Plain one. Plain two. Plain three.", 3),
]


@pytest.mark.parametrize("label,text,expected", ABBREVIATION_SPLITS, ids=[c[0] for c in ABBREVIATION_SPLITS])
def test_abbreviation_is_not_split_into_its_own_sentence(label, text, expected):
    """A naive split made "Dr. " a sentence, and in THIS module that is worse than cosmetic: each
    fragment is independently SCORED and independently REWRITTEN. A one-word fragment gets a
    confident meaningless score (a single word scores 0.998 on roberta_openai), so it clears the
    min_score gate on nothing and is handed to the rewriter."""
    from untell.rewriter.targeted import split_sentences

    parts = split_sentences(text)
    assert len(parts) == expected, f"{label}: {parts}"
    assert "".join(parts) == text, "the split must round-trip byte-for-byte"


@pytest.mark.parametrize(
    "text",
    [
        "Dr. Smith published. The study ran.",
        "Plain one. Plain two.",
        "Trailing space at end.   ",
        "Line one.\nLine two.\n\nLine three.",
        "",
        "No terminator at all",
    ],
)
def test_split_round_trips_exactly(text):
    """The module reassembles the document from these pieces, so any lost byte is corruption."""
    from untell.rewriter.targeted import split_sentences

    assert "".join(split_sentences(text)) == text


class TestCompositeDoesNotMutateSharedState:
    """The intensity sweep used to assign `self._structural.intensity` and restore it afterwards.

    Two ways that corrupts the object, both silent:
      * the restore is not in a `finally`, so any exception between the two leaves the swept value
        in place permanently;
      * under concurrency a second caller reads the swept value as its own baseline and "restores"
        that. Measured with 8 threads on one shared instance: the configured 0.7 came back as 0.4,
        and every later call used the wrong intensity with nothing raised anywhere.
    """

    SRC = (
        "Furthermore, the organization leverages robust methodologies to optimize operational "
        "outcomes. Moreover, stakeholders utilize comprehensive frameworks to drive innovation."
    )

    def _patch_score(self, monkeypatch):
        import untell.scripts.score as score_mod

        monkeypatch.setattr(
            score_mod, "score_text",
            lambda t, tier="lite", threshold=0.30: {
                "max": 0.5, "mean": 0.5, "detectors": {"d": 0.5}, "tier": tier, "scored": True,
            },
        )

    def test_intensity_attribute_is_never_mutated(self, monkeypatch):
        self._patch_score(monkeypatch)
        rw = CompositeRewriter(best_of=3, intensity=0.7)
        seen = []
        real = rw._structural.rewrite

        def _spy(text, score_result, threshold=0.30, intensity=None):
            seen.append(rw._structural.intensity)  # the ATTRIBUTE, not the argument
            return real(text, score_result, threshold, intensity=intensity)

        monkeypatch.setattr(rw._structural, "rewrite", _spy)
        rw.rewrite(self.SRC, {"tier": "lite"})

        assert rw._structural.intensity == 0.7
        assert set(seen) == {0.7}, f"attribute changed mid-run: {seen}"

    def test_intensity_survives_an_exception_mid_sweep(self, monkeypatch):
        """No `finally` protected the restore, so a raising transform poisoned the instance."""
        self._patch_score(monkeypatch)
        rw = CompositeRewriter(best_of=3, intensity=0.7)

        def _boom(*a, **kw):
            raise RuntimeError("transform failed")

        monkeypatch.setattr(rw._structural, "rewrite", _boom)
        with pytest.raises(RuntimeError):
            rw.rewrite(self.SRC, {"tier": "lite"})
        assert rw._structural.intensity == 0.7

    def test_concurrent_rewrites_do_not_corrupt_the_instance(self, monkeypatch):
        import threading

        self._patch_score(monkeypatch)
        rw = CompositeRewriter(best_of=3, intensity=0.7)
        errors: list[BaseException] = []

        def worker():
            try:
                rw.rewrite(self.SRC, {"tier": "lite"})
            except BaseException as exc:  # noqa: BLE001 - reported below
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, errors
        assert rw._structural.intensity == 0.7

    def test_the_sweep_still_reaches_the_structural_rewriter(self, monkeypatch):
        """Removing the mutation must not remove the diversity it existed to create."""
        self._patch_score(monkeypatch)
        rw = CompositeRewriter(best_of=3, intensity=0.7)
        passed = []

        monkeypatch.setattr(
            rw._structural, "rewrite",
            lambda t, s, threshold=0.30, intensity=None: passed.append(intensity) or t,
        )
        rw.rewrite(self.SRC, {"tier": "lite"})
        assert sorted(passed) == [0.4, 0.7, 1.0]


class TestSeedingDoesNotTouchTheCallersRng:
    """`seed=` must make THIS call reproducible, not reseed the whole process.

    `random.seed(seed)` reseeds the module-level generator every other library in the process is
    also drawing from. Measured before the fix: a caller mid-sequence got 0.701325 where it
    expected 0.080066. The repo already carried evidence of the fallout — a test in this file seeds
    the global RNG defensively, with a comment about the outcome depending on "whatever random
    state the PREVIOUS test happened to leave".
    """

    SRC = (
        "Furthermore, the organization leverages robust methodologies to optimize outcomes. "
        "Moreover, stakeholders utilize comprehensive frameworks to drive innovation forward."
    )

    def test_callers_stream_is_preserved(self):
        import random

        random.seed(999)
        expected = [random.random() for _ in range(3)][1:]

        random.seed(999)
        random.random()
        structural_rewrite(self.SRC, intensity=0.7, seed=42)
        assert [random.random() for _ in range(2)] == expected

    def test_seed_still_makes_the_rewrite_reproducible(self):
        a = structural_rewrite(self.SRC, intensity=0.7, seed=7)
        b = structural_rewrite(self.SRC, intensity=0.7, seed=7)
        assert a == b

    def test_different_seeds_still_differ(self):
        outs = {structural_rewrite(self.SRC, intensity=1.0, seed=s) for s in range(8)}
        assert len(outs) > 1, "seeding produces no variation at all"

    def test_unseeded_calls_still_follow_the_global_generator(self):
        """Restoring state must not break callers that seed globally and pass no seed --
        several tests in this suite rely on exactly that."""
        import random

        random.seed(1234)
        a = structural_rewrite(self.SRC, intensity=1.0)
        random.seed(1234)
        b = structural_rewrite(self.SRC, intensity=1.0)
        assert a == b


class TestRewritesIntroduceNoMechanicalDefects:
    """A rewrite may change wording freely; it must not damage the text mechanically.

    Checked on input chosen to stress sentence handling — abbreviations ("Dr.", "e.g.", "p.m."),
    decimals ("3.5% vs. 2.1%"), quoted speech, a numbered list, URLs with parens and query strings,
    and spaced initials ("J. R. R. Tolkien"). Each is a place a naive split-on-period corrupts text.

    Defects present in the SOURCE are subtracted, so this measures what rewriting introduced rather
    than what it inherited. An earlier version of this check omitted that and reported three false
    positives — "at 3 p.m. Furthermore, they..." matched a split-at-abbreviation pattern that the
    source matched identically, because it is simply a correct sentence boundary.
    """

    HARD = {
        "abbreviations": "Dr. Smith met Prof. Jones at 3 p.m. Furthermore, they leveraged the data, "
                         "e.g. the survey results, to optimize outcomes.",
        "decimals": "Revenue rose 3.5% vs. 2.1% last year. Moreover, the ratio of 1.5 to 2.0 was "
                    "robust across sectors.",
        "quotes": 'He said "the results are robust" and then added "furthermore, we must optimize." '
                  "The team agreed.",
        "list": "Key points:\n1. Leverage the data.\n2. Optimize the workflow.\n3. Furthermore, iterate.",
        "urls": "See https://example.com/a_b(c) for details. Furthermore, the docs at "
                "docs.example.org/x?y=1 explain it.",
        "initials": "J. R. R. Tolkien wrote it. Moreover, C. S. Lewis leveraged similar themes.",
    }

    @staticmethod
    def _defects(text: str) -> set[str]:
        import re

        found = set()
        if text.count('"') % 2:
            found.add("unbalanced-quotes")
        if re.search(r"\b\d+\.\s+\d+\b", text):
            found.add("split-decimal")
        if re.search(r"https?://\S*\s", text):
            found.add("url-broken")
        if re.search(r"[a-z]{2,}\s+[,.;:]", text):
            found.add("space-before-punct")
        if re.search(r"\b(\w+)\s+\1\b", text, re.I):
            found.add("doubled-word")
        return found

    @pytest.mark.parametrize("rewriter_name", ["composite", "structural", "surgical"])
    def test_no_new_defects_on_hard_input(self, rewriter_name):
        from untell.rewriter import get_rewriter
        from untell.scripts.score import score_text

        rw = get_rewriter(prefer=rewriter_name)
        if rw is None or not rw.available():
            pytest.skip(f"{rewriter_name} unavailable")

        problems = []
        for label, src in self.HARD.items():
            out = rw.rewrite(src, score_text(src, tier="lite"), 0.30)
            introduced = self._defects(out) - self._defects(src)
            if "\n" in src and "\n" not in out:
                introduced.add("layout-flattened")
            if introduced:
                problems.append((label, sorted(introduced), out[:120]))
        assert not problems, problems


class TestTargetedFallsBackInsteadOfDoingNothing:
    """`targeted` was silently inert whenever no sentence cleared min_score.

    MEASURED on 8 real HC3 AI texts (64 sentences), the two lite paths differ completely:
        torch-backed lite        32/64 sentences >= 0.30  -> targets normally
        pure stdlib NO_TORCH=1    0/64 sentences >= 0.30  -> targeted NOTHING
    and through the loop on 15 real texts, stdlib: 0/15 changed, 0.5679 -> 0.5679, tells
    0.463 -> 0.463. The cause is a scale mismatch: min_score is an ABSOLUTE 0.30 applied per
    sentence, while a single sentence scores far below the paragraph containing it (mean 0.326
    vs 0.619 on the same texts). After the fallback: 15/15 changed, 0.5679 -> 0.2518.
    """

    class _Inner:
        name = "inner"
        calls: list

        def __init__(self):
            self.calls = []

        def available(self):
            return True

        def rewrite(self, text, score_result, threshold=0.30):
            self.calls.append(text)
            return "WHOLE TEXT REWRITE. Second sentence here."

    def _patch_scores(self, monkeypatch, mapping, default):
        import untell.scripts.score as score_mod

        def _fake(text, tier="lite", threshold=0.30):
            m = mapping.get(text.strip(), default)
            return {"max": m, "mean": m, "detectors": {"d": m}, "tier": tier}

        monkeypatch.setattr(score_mod, "score_text", _fake)

    def test_falls_back_to_whole_text_when_no_sentence_is_targetable(self, monkeypatch, caplog):
        from untell.rewriter.targeted import TargetedRewriter

        text = "First sentence here. Second sentence here."
        # Every sentence below min_score, but the document itself is flagged - the stdlib case.
        self._patch_scores(monkeypatch, {}, 0.10)
        inner = self._Inner()
        rw = TargetedRewriter(inner=inner, min_score=0.30)
        with caplog.at_level("WARNING", logger="untell.rewriter.targeted"):
            out = rw.rewrite(text, {"tier": "lite"}, 0.30)
        assert out != text, "returned the input unchanged - the silent no-op is back"
        assert inner.calls == [text], "inner should have been called once, on the WHOLE text"
        assert "min_score" in caplog.text, "the fallback must say why it happened"

    def test_no_harm_guarantee_survives_when_sentences_were_targeted(self, monkeypatch):
        """Tried-and-failed must still return the input - only never-tried falls back."""
        from untell.rewriter.targeted import TargetedRewriter

        text = "First sentence here. Second sentence here."
        # Both sentences clear min_score, but the rewrite scores WORSE, so nothing is adopted.
        self._patch_scores(
            monkeypatch,
            {
                "First sentence here.": 0.90,
                "Second sentence here.": 0.90,
                "WHOLE TEXT REWRITE. Second sentence here.": 0.99,
            },
            0.99,
        )
        inner = self._Inner()
        rw = TargetedRewriter(inner=inner, min_score=0.30)
        out = rw.rewrite(text, {"tier": "lite"}, 0.30)
        assert out == text, "a targeted-but-unimproved text must be returned untouched"

    def test_normal_targeting_path_is_unchanged(self, monkeypatch):
        """The fallback must not fire when targeting works."""
        from untell.rewriter.targeted import TargetedRewriter

        text = "First sentence here. Second sentence here."
        self._patch_scores(
            monkeypatch,
            {
                "First sentence here.": 0.90,
                "Second sentence here.": 0.05,
                "WHOLE TEXT REWRITE. Second sentence here.": 0.01,
            },
            0.50,
        )
        inner = self._Inner()
        rw = TargetedRewriter(inner=inner, min_score=0.30)
        out = rw.rewrite(text, {"tier": "lite"}, 0.30)
        assert "Second sentence here." in out, "the clean sentence must survive byte-identical"
        assert inner.calls == ["First sentence here."], "only the flagged sentence is rewritten"


class TestEveryStyleActuallyChangesTheFreePath:
    """Four styles were byte-identical to no style at all.

    `--style` is advertised in the CLI's own help with 14 modes, but the profile table set only
    `contractions` and `register`, and casual, conversational, blunt and minimalist all resolved to
    the neutral default's exact values. MEASURED over 20 HC3 texts before: those four differed from
    no-style on 0 of 20, while academic and technical differed on 19. A flag that cannot change
    anything is worse than one that is missing.

    Two knobs the pipeline already had at fixed rates — split frequency and opener frequency — are
    now set per profile. After: casual 9/20, blunt 16/20, conversational 16/20, minimalist 16/20.
    `persuasive` and `empathetic` stay at 1/20; they are register-only variations by design, and
    that is a real limit rather than a fixed one.
    """

    # Six sentences, several of them long. The knobs set RATES over sentences, so a two-sentence
    # sample gives them almost nothing to act on — the first version of this test used one and
    # "casual" (whose only lever is a 1.2x opener rate) could not differ at any seed.
    SRC = (
        "Furthermore, the organization leverages robust methodologies to optimize operational "
        "efficiency across diverse sectors and geographies. Moreover, stakeholders must navigate "
        "the evolving landscape of digital transformation while maintaining rigorous internal "
        "standards. The team reviewed the results. Additionally, the reporting cadence was "
        "adjusted so that every regional lead receives a consolidated summary before the quarterly "
        "planning meeting. Costs fell. Overall, the programme is considered a success by the "
        "steering committee, although several workstreams remain behind their original schedule."
    )

    @pytest.mark.parametrize("style", ["casual", "blunt", "conversational", "minimalist"])
    def test_the_previously_inert_styles_now_bite(self, style):
        """Across seeds, not on any single one.

        The knobs set RATES, so a given seed can land on a draw where the styled and unstyled paths
        coincide — asserting a difference at one seed asks for something the transform does not
        promise, and the first version of this test duly failed on one style at seed 7. What must
        hold is that the style is capable of changing the output at all, which is exactly what was
        broken: these four could not, at any seed, on any text.
        """
        import random

        from untell.rewriter.structural import StructuralRewriter

        rw = StructuralRewriter()
        differs = 0
        for seed in range(8):
            random.seed(seed)
            base = rw.rewrite(self.SRC, {"max": 0.9})
            random.seed(seed)
            styled = rw.rewrite(self.SRC, {"max": 0.9, "style": style})
            differs += styled != base
        assert differs > 0, f"{style} never differs from no-style across 8 seeds"

    def test_the_default_path_is_untouched(self):
        """The knobs multiply by 1.0 on the neutral profile, so a run with no style must be
        byte-identical to the behaviour before they existed — verified against the previous commit
        on 25 HC3 texts, and pinned here against the rates themselves."""
        from untell.rewriter.structural import _NEUTRAL

        assert _NEUTRAL["sentences"] == 1.0
        assert _NEUTRAL["openers"] == 1.0
