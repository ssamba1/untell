"""Tests for the added attack/defense modules: word-importance substitution + unicode tricks."""

from __future__ import annotations

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
