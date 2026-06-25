"""Preserve-lock round-trip tests."""

from __future__ import annotations

from humanize.scripts.preserve import lock, restore


def _roundtrip(text: str) -> None:
    masked, mapping = lock(text)
    assert restore(masked, mapping) == text


def test_roundtrip_plain():
    _roundtrip("A perfectly ordinary sentence with no protected spans at all.")


def test_roundtrip_numeric_citation():
    _roundtrip("The effect was robust [12] and replicated in later work [3, 4].")


def test_roundtrip_author_year():
    _roundtrip("As Smith (2020) argued, and others agreed (Lee & Park, 2019, p. 4).")


def test_roundtrip_numbers_and_units():
    _roundtrip("The sample of 1,024 subjects showed a 42% increase over 3.5 years.")


def test_roundtrip_quotes_and_url():
    _roundtrip('She said "this changes everything" and cited https://example.com/x?y=1.')


def test_citation_is_masked_and_unchanged():
    text = "The result holds [12]."
    masked, mapping = lock(text)
    assert "[12]" not in masked  # the span was replaced by a sentinel
    assert "[12]" in mapping.values()  # and preserved verbatim in the mapping
    assert restore(masked, mapping) == text


def test_numbers_preserved_through_simulated_rewrite():
    text = "We observed 95% accuracy across 5 trials."
    masked, mapping = lock(text)
    # Simulate a rewrite that reorders prose but keeps sentinels intact.
    sentinels = list(mapping.keys())
    rewritten = "Across the trials we logged strong accuracy: " + ", ".join(sentinels) + "."
    restored = restore(rewritten, mapping)
    for original in mapping.values():
        assert original in restored


def test_empty_text():
    masked, mapping = lock("")
    assert masked == ""
    assert mapping == {}
    assert restore(masked, mapping) == ""
