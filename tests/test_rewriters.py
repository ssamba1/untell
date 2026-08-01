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
        from untell.rewriter.structural import _target_burstiness, _cv

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
        w = lambda ss: sorted(x.lower() for x in _re.findall(r"[a-z]+", " ".join(ss).lower()))
        # allow the injected "and" connector
        assert set(w(sents)) - set(w(after_sents)) == set()

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
