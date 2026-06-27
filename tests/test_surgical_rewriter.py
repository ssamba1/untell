"""Tests for the no-key SurgicalRewriter and its wiring into get_rewriter / the loop."""

from untell.rewriter import SurgicalRewriter, get_rewriter
from untell.rewriter.base import Rewriter


def test_surgical_is_always_available():
    rw = SurgicalRewriter()
    assert rw.available() is True
    assert rw.name == "surgical"


def test_surgical_satisfies_rewriter_protocol():
    assert isinstance(SurgicalRewriter(), Rewriter)


def test_get_rewriter_prefer_surgical_returns_it_with_no_key(monkeypatch):
    # Even with no API key and no policy dir, prefer="surgical" yields a runnable rewriter.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("UNTELL_POLICY_DIR", raising=False)
    rw = get_rewriter(prefer="surgical")
    assert rw is not None
    assert rw.name == "surgical"


def test_surgical_rewrite_returns_text_and_preserves_sentinels():
    rw = SurgicalRewriter()
    text = "Furthermore, organizations leverage numerous robust and innovative solutions ⟦HZ0001⟧."
    out = rw.rewrite(text, {"tier": "lite"}, threshold=0.30)
    assert isinstance(out, str) and out.strip()
    # The opaque sentinel must survive substitution untouched (the loop relies on this).
    assert "⟦HZ0001⟧" in out


def test_surgical_rewrite_does_not_raise_on_empty():
    rw = SurgicalRewriter()
    assert isinstance(rw.rewrite("", {"tier": "lite"}), str)


def test_surgical_normalizes_composite_tier_label():
    # A browser scorer hands back a non-scoreable composite tier; the rewriter must not crash.
    rw = SurgicalRewriter()
    out = rw.rewrite("Furthermore we utilize robust solutions.", {"tier": "browser:zerogpt"})
    assert isinstance(out, str)
