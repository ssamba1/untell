"""Tests for the added attack/defense modules: word-importance substitution + unicode tricks."""

from __future__ import annotations

import re

import pytest

from untell.attacks import (
    count_hidden,
    homoglyph_substitute,
    importance,
    scrub_hidden,
    surgical_substitute,
    synonyms,
)

AI = (
    "Artificial intelligence has fundamentally transformed numerous industries. Moreover, it "
    "utilizes various significant algorithms to optimize crucial operations."
)


def test_every_synonym_key_is_reachable_by_the_tokenizer():
    """A key the tokenizer can never produce is dead code that looks exactly like live code.

    Both consumers — synonyms() and rewriter/structural._plain_register — look words up one token
    at a time, so "represents a" could never match, and under the old bare [A-Za-z]+ pattern
    neither could any hyphenated key. That silently killed six of the most recognisable tells in
    the catalogue (cutting-edge, state-of-the-art, world-class, best-in-class, top-tier,
    next-level) while the comment above the table claimed phrases were matched.
    """
    from untell.attacks.word_importance import _SYN, _WORD

    unreachable = [k for k in _SYN if not _WORD.fullmatch(k)]
    assert not unreachable, f"these _SYN keys can never be looked up: {unreachable}"


def test_no_synonym_entry_lists_its_own_key():
    """A word listed as its own synonym makes surgical_substitute score a candidate identical to
    the current text — a wasted detector pass that can never beat the improvement threshold."""
    from untell.attacks.word_importance import _SYN

    offenders = {k: v for k, v in _SYN.items() if k.lower() in [s.lower() for s in v]}
    assert not offenders, f"self-synonyms waste a scoring call each: {offenders}"


class TestASubstitutionDoesNotDoubleAParticle:
    """A substitution is a one-token swap, so a multi-word replacement ending in a particle repeats
    whichever particle the sentence already supplies.

    30 of the table's multi-word values end in one, which makes this a property of the mechanism
    rather than of any entry — the table cannot know what follows the word. Measured on natural
    sentences before the fix:

        "navigate through the complexities" -> "work through THROUGH the complexities"
        "navigating through a transition"   -> "working through THROUGH a transition"
        "a myriad of options"               -> "a scores of OF options"
    """

    CASES = [
        ("The team will navigate through the regulatory complexities.", "navigate", "work through",
         "The team will work through the regulatory complexities."),
        ("They are navigating through a difficult transition.", "navigating", "working through",
         "They are working through a difficult transition."),
        # "a myriad of" is a quantifier FRAME, so the whole thing goes — see the class below.
        # Collapsing the doubled "of" alone would leave "a scores of options".
        ("The report offers a myriad of options to weigh.", "myriad", "scores of",
         "The report offers scores of options to weigh."),
    ]

    @pytest.mark.parametrize(("sentence", "word", "rep", "expected"), CASES)
    def test_the_seam_collapses(self, sentence, word, rep, expected):
        from untell.attacks.word_importance import substitute_once

        assert substitute_once(sentence, word, rep) == expected

    def test_a_different_particle_is_kept(self):
        """"embark on" -> "set out on": the replacement ends in "out", not "on"; nothing to drop."""
        from untell.attacks.word_importance import substitute_once

        out = substitute_once("The company will embark on a long programme.", "embark", "set out")
        assert out == "The company will set out on a long programme."

    def test_a_hyphenated_compound_is_not_a_duplicate(self):
        """"the reason for for-profit companies": the second "for" starts a compound word."""
        from untell.attacks.word_importance import substitute_once

        out = substitute_once("The reason for for-profit firms is margin.", "reason", "case for")
        assert out == "The case for for-profit firms is margin."

    @pytest.mark.parametrize("sentence", [c[0] for c in CASES])
    def test_the_structural_path_collapses_it_too(self, sentence):
        """_plain_register is the other consumer of the same table and had the same seam."""
        import random

        from untell.rewriter.structural import _plain_register

        random.seed(0)
        words = _plain_register(sentence, intensity=1.0).split()
        doubled = [f"{a} {b}" for a, b in zip(words, words[1:]) if a.lower() == b.lower()]
        assert not doubled, doubled

    def test_no_particle_is_itself_a_substitutable_key(self):
        """The structural path lets a match consume the following particle, which would hide it
        from substitution in its own right. Safe only while no particle is a key."""
        from untell.attacks.word_importance import _PARTICLES, _SYN

        assert not (_PARTICLES & set(_SYN))


class TestQuantifierFramesAreRewrittenWhole:
    """"a myriad of X" carries its article and its "of" as part of the construction.

    Swapping the middle token alone cannot be grammatical, and the table is single-token by design
    (a test above enforces it), so the frame has to be handled as a unit. MEASURED coming out of
    the composite rewriter before the fix:

        "a myriad of options"    -> "a many of options" / "a countless of options"
        "a plethora of evidence" -> "a lots of evidence" / "a many of evidence"
    """

    FRAMES = [
        ("The report offers a myriad of options to weigh.", "myriad"),
        ("There is a plethora of evidence supporting it.", "plethora"),
        ("Researchers examined a myriad of factors in the cohort.", "myriad"),
    ]

    # Bare counting quantifiers: grammatical on their own ("many options"), never after an article.
    # "a wealth of evidence" is fine — `wealth` is a noun, so it keeps the frame it came from.
    BARE = r"\ban? (many|countless|lots|scores|plenty|several|numerous)\b"

    @pytest.mark.parametrize(("sentence", "key"), FRAMES)
    def test_no_replacement_leaves_a_stranded_article(self, sentence, key):
        from untell.attacks.word_importance import _SYN, substitute_once

        for option in _SYN[key]:
            out = substitute_once(sentence, key, option)
            assert not re.search(self.BARE, out, re.IGNORECASE), (option, out)
            assert " of of " not in out, (option, out)

    def test_a_count_quantifier_is_refused_on_a_mass_noun(self):
        """"a plethora of evidence" -> "many evidence" is wrong for the same reason "many water"
        is. The frame hides it, because it reads naturally with count and mass heads alike."""
        from untell.attacks.word_importance import substitute_once

        sentence = "There is a plethora of evidence supporting it."
        assert substitute_once(sentence, "plethora", "many") == sentence  # refused, not mangled
        assert "a wealth of evidence" in substitute_once(sentence, "plethora", "wealth")
        assert "lots of evidence" in substitute_once(sentence, "plethora", "lots")

    def test_a_count_quantifier_is_allowed_on_a_plural_head(self):
        from untell.attacks.word_importance import substitute_once

        out = substitute_once("The report offers a myriad of options.", "myriad", "many")
        assert out == "The report offers many options."

    def test_the_head_noun_is_never_consumed(self):
        from untell.attacks.word_importance import substitute_once

        out = substitute_once("It lists a myriad of options today.", "myriad", "countless")
        assert out == "It lists countless options today."

    def test_capitalisation_at_a_sentence_start_survives(self):
        from untell.attacks.word_importance import substitute_once

        out = substitute_once("A myriad of options exist here.", "myriad", "countless")
        assert out == "Countless options exist here."

    @pytest.mark.parametrize(("sentence", "key"), FRAMES)
    def test_the_structural_path_agrees(self, sentence, key):
        import random

        from untell.rewriter.structural import _plain_register

        for seed in range(12):
            random.seed(seed)
            out = _plain_register(sentence, intensity=1.0)
            assert not re.search(self.BARE, out, re.IGNORECASE), (seed, out)
            assert "many evidence" not in out, (seed, out)

    def test_a_bare_key_outside_the_frame_still_substitutes(self):
        """The frame rule must not disable the ordinary swap."""
        from untell.attacks.word_importance import substitute_once

        out = substitute_once("Myriad options exist here.", "Myriad", "Countless")
        assert out == "Countless options exist here."


def test_hyphenated_tells_are_actually_substituted():
    """The end-to-end consequence of the tokenizer fix, not just the table's shape."""
    import random

    from untell.rewriter.structural import _plain_register

    random.seed(0)
    src = "Our cutting-edge, state-of-the-art platform delivers world-class results."
    out = _plain_register(src, intensity=1.0)
    for tell in ("cutting-edge", "state-of-the-art", "world-class"):
        assert tell not in out, f"{tell} survived the plain-register pass"


def test_surgical_substitute_scores_the_original_once(monkeypatch):
    """surgical_substitute computed `pre`, then importance() recomputed the identical baseline —
    two byte-identical detector passes over the same text at the same tier on every call. On the
    full tier that is a whole multi-model ensemble pass spent on a value already in hand."""
    import untell.attacks.word_importance as wi

    src = (
        "Furthermore, artificial intelligence has fundamentally transformed numerous industries. "
        "Moreover, organizations leverage robust methodologies to optimize crucial outcomes."
    )
    seen: list[str] = []

    def _spy(text, **kw):
        seen.append(text)
        return {"max": 0.9, "mean": 0.9, "detectors": {"fake": 0.9}, "scored": True}

    monkeypatch.setattr(wi, "score_text", _spy)
    monkeypatch.setattr(
        wi, "batch_score_texts",
        lambda texts, **kw: [{"max": 0.9, "mean": 0.9, "detectors": {"fake": 0.9}} for _ in texts],
    )

    wi.surgical_substitute(src, tier="lite", max_subs=4)
    assert seen.count(src) == 1, f"scored the original {seen.count(src)} times"


def test_importance_accepts_a_precomputed_base(monkeypatch):
    import untell.attacks.word_importance as wi

    def _boom(text, **kw):
        raise AssertionError("importance recomputed the baseline despite being given one")

    monkeypatch.setattr(wi, "score_text", _boom)
    monkeypatch.setattr(
        wi, "batch_score_texts",
        lambda texts, **kw: [{"max": 0.5, "mean": 0.5, "detectors": {"fake": 0.5}} for _ in texts],
    )
    ranks = wi.importance("robust seamless delve utilize", tier="lite", base=0.8)
    assert ranks and all(abs(d - 0.3) < 1e-9 for _, d in ranks)  # 0.8 base - 0.5 stripped


def test_synonyms_known_word():
    syns = synonyms("numerous")
    assert "many" in [s.lower() for s in syns]


def test_importance_ranks_words():
    ranked = importance(AI, tier="lite")
    assert ranked and isinstance(ranked[0], tuple)
    # scores are detector-drop deltas; the list is sorted descending
    assert ranked[0][1] >= ranked[-1][1]


def test_surgical_substitute_lowers_or_holds_score():
    r = surgical_substitute(AI, tier="lite", max_subs=6)
    assert r["post"] <= r["pre"] + 1e-9
    assert isinstance(r["text"], str) and r["text"]
    assert r["substitutions"] >= 0


# --- unicode tricks ---

def test_homoglyph_then_scrub_roundtrips_to_ascii():
    h = homoglyph_substitute("america cocoa", rate=1.0)  # replace every eligible letter
    assert h != "america cocoa"  # something changed
    assert count_hidden(h) > 0
    assert h.encode("ascii", "ignore").decode() != h  # contains non-ascii
    assert scrub_hidden(h) == "america cocoa"  # scrub restores ASCII


def test_scrub_removes_zero_width_and_controls():
    dirty = "hel​lo‍ wor﻿ld"  # zero-width chars embedded
    assert count_hidden(dirty) >= 2
    clean = scrub_hidden(dirty)
    assert clean == "hello world"
    assert count_hidden(clean) == 0


def test_homoglyph_rate_zero_is_noop():
    assert homoglyph_substitute("hello", rate=0.0) == "hello"


def test_scrub_preserves_legitimate_unicode():
    # Regression: scrub must not corrupt legitimate Unicode (emoji ZWJ sequences, variation
    # selectors, superscripts) while still stripping watermark carriers.
    family = "\U0001f468‍\U0001f469‍\U0001f467‍\U0001f466"  # family emoji
    assert scrub_hidden(family) == family                  # structural ZWJ kept
    assert scrub_hidden("❤️") == "❤️"  # heart keeps its VS16 emoji presentation
    assert scrub_hidden("E=mc²") == "E=mc²"      # superscript survives (NFC, not NFKC)
    assert scrub_hidden("wor‍ld") == "world"          # but an orphan ZWJ watermark is removed
