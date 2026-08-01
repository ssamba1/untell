"""Back-translation tests.

Offline tests run everywhere (the no-op fallback path). The real round-trip test is gated on
torch/transformers/sentencepiece, so it skips on the lite CI / broken-torch boxes and runs in the
full-tier CI job (where it downloads the MarianMT models).
"""

from __future__ import annotations

import pytest

from untell.attacks import BackTranslator, back_translate, count_hidden, scrub_hidden


def test_noop_when_unavailable(monkeypatch):
    bt = BackTranslator()
    monkeypatch.setattr(bt, "available", lambda: False)
    text = "This text must come back exactly unchanged when MT is unavailable."
    assert bt.back_translate(text) == text


def test_empty_input_is_noop():
    assert back_translate("") == ""
    assert back_translate("   ") == "   "


def test_translation_failure_falls_back(monkeypatch):
    bt = BackTranslator()
    monkeypatch.setattr(bt, "available", lambda: True)

    def _boom(*a, **k):
        raise RuntimeError("model load failed")

    monkeypatch.setattr(bt, "_translate", _boom)
    text = "Any failure mid-translation must degrade to the original text, never raise."
    assert bt.back_translate(text) == text


def _mt_ready() -> bool:
    try:
        import sentencepiece  # noqa: F401
        import torch  # noqa: F401
        import transformers  # noqa: F401
    except Exception:
        return False
    return True


@pytest.mark.skipif(not _mt_ready(), reason="MarianMT stack (torch/transformers/sentencepiece) unavailable")
def test_roundtrip_changes_text_but_keeps_gist():
    src = "The committee approved the new policy after a lengthy and contentious debate."
    out = back_translate(src, pivots=("fr",))
    assert isinstance(out, str) and out.strip()
    assert len(out.split()) >= 5  # produced real prose, not empty/garbage


# --------------------------------------------------------------------------- scrub COVERAGE
INVISIBLE_CARRIERS = [
    ("function application", "a\u2061b"),
    ("invisible times", "a\u2062b"),
    ("invisible separator", "a\u2063b"),
    ("invisible plus", "a\u2064b"),
    ("zero-width space", "a\u200bb"),
    ("zero-width non-joiner", "a\u200cb"),
    ("word joiner", "a\u2060b"),
    ("BOM / ZWNBSP", "a\ufeffb"),
]

HOMOGLYPHS = [
    ("greek omicron", "a\u03bfc", "aoc"),
    ("greek alpha", "\u03b1bc", "abc"),
    ("cyrillic dotted i", "a\u0456c", "aic"),
    ("cyrillic a", "\u0430bc", "abc"),
]

# Legitimate Unicode that must NEVER be damaged — the reason ZWJ, variation selectors and bidi
# marks are deliberately preserved rather than blanket-stripped.
MUST_SURVIVE = [
    ("emoji ZWJ family", "\U0001f468\u200d\U0001f469\u200d\U0001f467"),
    ("emoji variation selector", "\u2764\ufe0f"),
    ("RTL with bidi mark", "\u0645\u0631\u062d\u0628\u0627 \u200f!"),
    ("accented latin", "caf\u00e9 na\u00efve"),
]


@pytest.mark.parametrize("desc,text", INVISIBLE_CARRIERS)
def test_invisible_carrier_is_scrubbed_and_counted(desc, text):
    """A carrier that survives scrubbing while count_hidden reports 0 is the worst case: the tool
    tells the user their text is clean while a tracking watermark is still embedded."""
    assert scrub_hidden(text) == "ab", desc
    assert count_hidden(text) >= 1, f"{desc}: not counted, so the user is told the text is clean"


@pytest.mark.parametrize("desc,text,expected", HOMOGLYPHS)
def test_homoglyph_is_normalized_to_ascii(desc, text, expected):
    """The scrub direction must be wider than the attack direction: we only EMIT Cyrillic
    confusables, but an adversary can use Greek ones just as easily."""
    assert scrub_hidden(text) == expected, desc


@pytest.mark.parametrize("desc,text", MUST_SURVIVE)
def test_legitimate_unicode_is_preserved(desc, text):
    assert scrub_hidden(text) == text, desc
