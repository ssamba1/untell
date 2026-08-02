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


class _FakeTok:
    """Tokenizer stand-in: 2 BPE tokens per word, matching MarianMT's rough ratio."""

    def __call__(self, text, **kwargs):
        if isinstance(text, list):
            text = text[0]
        return {"input_ids": list(range(len(text.split()) * 2))}


def test_long_input_is_chunked_not_silently_truncated():
    """truncation=True discards everything past 512 tokens and returns the partial translation as
    if it were complete — no exception, no warning. A ~400-word document lost its tail."""
    bt = BackTranslator()
    long_text = " ".join(f"This is sentence number {i} about a topic." for i in range(60))
    chunks = bt._chunk(long_text, _FakeTok())

    assert len(chunks) > 1, "long input must be split"
    # Nothing may be dropped: rejoining the chunks must reproduce every word.
    assert " ".join(chunks).split() == long_text.split()


def test_short_input_stays_a_single_chunk():
    bt = BackTranslator()
    assert len(bt._chunk("Hello there. How are you?", _FakeTok())) == 1


CHUNK_SHAPES = {
    # The existing coverage is all many-short-sentences, the one shape where the size guard fires.
    "one long sentence, no clause breaks": " ".join(["word"] * 900) + ".",
    "one long sentence with commas": ", ".join(" ".join(["word"] * 60) for _ in range(15)) + ".",
    "long sentence followed by short ones": " ".join(["word"] * 800) + ". Short one. Another.",
    "two long sentences": " ".join(["alpha"] * 700) + ". " + " ".join(["beta"] * 700) + ".",
    "one very long word-salad clause": " ".join(["supercalifragilistic"] * 600) + ".",
}


@pytest.mark.parametrize("text", CHUNK_SHAPES.values(), ids=list(CHUNK_SHAPES))
def test_no_chunk_exceeds_the_token_budget(text):
    """The size test was skipped for a chunk's first sentence (`if current and ...`), so a single
    sentence over the budget could never be split — it passed through whole and _translate's
    truncation=True silently dropped everything past 512 tokens, returning the partial translation
    as if it were complete. Asserting the invariant, not the symptom: no chunk over budget, and no
    word lost."""
    bt = BackTranslator()
    tok = _FakeTok()
    chunks = bt._chunk(text, tok)

    budget = bt._MAX_TOKENS - 16
    assert chunks
    for c in chunks:
        assert len(tok(c)["input_ids"]) <= budget, f"chunk of {len(c.split())} words exceeds budget"
    assert " ".join(chunks).split() == text.split(), "chunking dropped or reordered words"


def test_chunking_never_returns_empty():
    """A degenerate input must still yield something translatable rather than an empty list."""
    bt = BackTranslator()
    assert bt._chunk("no terminator here", _FakeTok()) == ["no terminator here"]


# count_hidden has now lost THREE carrier classes one at a time (invisible math operators, orphan
# ZWJ, C0/C1 controls), each shipping a report that said "0 hidden characters" while scrub_hidden
# silently changed the text. Fixing carriers one by one does not prevent a fourth. This pins the
# INVARIANT instead: for carriers that are removed (as opposed to homoglyphs, which are replaced
# in place), the count must equal the number of characters scrubbing actually removes.
SYNC_CASES = [
    "a\u0001b",              # C0 control
    "a\u001fb\u200cc",       # C1 control + zero-width non-joiner
    "a\u200bb",              # zero-width space
    "a\u2062b",              # invisible times
    "hel\u200dlo",           # orphan ZWJ
    "a\u0007\u200b\u2061b",  # bell + ZWSP + function application
    "plain text",            # nothing to remove
    "",                      # degenerate
]


@pytest.mark.parametrize("text", SYNC_CASES)
def test_count_hidden_matches_what_scrub_hidden_removes(text):
    removed = len(text) - len(scrub_hidden(text))
    assert count_hidden(text) == removed, (
        f"count_hidden reported {count_hidden(text)} but scrubbing removed {removed} chars from "
        f"{text!r} — a caller would be told the text is clean while it is silently modified"
    )


def test_wordnet_is_probed_once_not_per_word():
    """A failed import is not cached by Python — it re-scans sys.path every single time.

    `synonyms()` did `from nltk.corpus import wordnet` inside a try/except on every call, which
    reads as free when nltk is absent. MEASURED in a warm loop profile, it was the single largest
    non-model cost:

        7389 find_spec calls, every one for 'nltk'
        36720 _path_join, 7344 nt.stat, ~0.6s of pure import machinery

    Isolated: 400 synonym lookups took 140.0 ms re-importing each time versus 0.9 ms with the probe
    cached — 153x. After the fix the same loop run makes ZERO find_spec calls.
    """
    import importlib._bootstrap_external as be

    from untell.attacks import word_importance as wi

    wi._wordnet_cache = wi._WORDNET_UNSET  # force a cold probe

    seen = []
    original = be.FileFinder.find_spec

    def spy(self, fullname, target=None):
        if fullname.split(".")[0] == "nltk":
            seen.append(fullname)
        return original(self, fullname, target)

    def probe_cost(n_words: int) -> int:
        """find_spec calls for nltk while looking up ``n_words`` synonyms, from a cold probe."""
        wi._wordnet_cache = wi._WORDNET_UNSET
        seen.clear()
        be.FileFinder.find_spec = spy
        try:
            for i in range(n_words):
                wi.synonyms(f"leverage{i % 3}")
        finally:
            be.FileFinder.find_spec = original
        return len(seen)

    # A single failed import scans EVERY sys.path entry, so the absolute count depends on the
    # environment. The invariant that matters is that it does not scale with the number of words:
    # one probe per process, not one per lookup.
    few, many = probe_cost(3), probe_cost(30)
    assert many <= few, f"nltk probe scales with word count: {few} calls for 3 words, {many} for 30"


def test_synonyms_still_returns_builtin_entries():
    """The probe must not disturb the built-in map, which is the path that always works."""
    from untell.attacks.word_importance import synonyms

    assert "use" in synonyms("leverage")
    assert synonyms("zzzznotaword") == []


NFC_SINGLETONS = [
    ("greek question mark", ";", ";"),
    ("greek varia", "`", "`"),
    ("kelvin sign", "K", "K"),
]


@pytest.mark.parametrize("desc,ch,ascii_form", NFC_SINGLETONS)
def test_nfc_singletons_are_counted_not_just_scrubbed(desc, ch, ascii_form):
    """scrub_hidden ends with an NFC pass, and NFC itself rewrites singleton confusables.

    Measured: each of these was silently replaced while count_hidden reported 0 — so the scrub
    report claimed the text was clean and the text had changed. Fourth carrier class to go missing
    from that function, which is why it is now counted the way it is applied (by asking NFC) rather
    than by listing three codepoints and waiting for a fifth.
    """
    text = f"abc{ch}def"
    assert scrub_hidden(text) == f"abc{ascii_form}def", desc
    assert count_hidden(text) >= 1, f"{desc}: scrubbed but reported as clean"


@pytest.mark.parametrize(
    "desc,text",
    [
        ("plain ascii", "The cat sat on the mat."),
        ("emoji zwj family", "\U0001f468‍\U0001f469‍\U0001f467"),
        ("variation selector", "❤️"),
        ("rtl with bidi mark", "مرحبا ‏!"),
        ("precomposed accents", "café naïve résumé"),
        ("CJK", "人工智能"),
        ("superscript and ligature", "x² and ﬁne"),
    ],
)
def test_legitimate_unicode_is_not_counted_as_hidden(desc, text):
    """Counting per CHARACTER keeps real composition out of it: "e" + combining acute normalises as
    a pair but neither character changes alone, so only true singletons are counted. Otherwise every
    accented document would report as watermarked."""
    assert count_hidden(text) == 0, desc
