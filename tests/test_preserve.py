"""Preserve-lock round-trip tests."""

from __future__ import annotations

import json

from untell.scripts.preserve import lock, restore
from untell.scripts.preserve import main as preserve_main


def test_cli_is_ascii_safe(capsys):
    rc = preserve_main(["Smith (2020) reported 42% across [3] cases."])
    assert rc == 0
    out = capsys.readouterr().out
    out.encode("ascii")  # sentinels escaped to \\u27e6 — never crash a Windows cp1252 stdout
    parsed = json.loads(out)
    assert "masked" in parsed and "mapping" in parsed
    assert parsed["mapping"]  # something was locked


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


def test_sentinel_regex_handles_5plus_digit_overflow():
    # lock() numbers sentinels f"⟦HZ{i:04d}⟧" (min width 4) -> 5 digits once a doc has >9999 locked
    # spans. restore()/find_sentinels MUST still match those, or the locked span is silently dropped.
    from untell.scripts.preserve import _SENTINEL_RE, find_sentinels

    assert _SENTINEL_RE.fullmatch("⟦HZ10000⟧")  # 5 digits
    assert _SENTINEL_RE.fullmatch("⟦HZ0007⟧")  # 4 digits still ok
    masked = "alpha ⟦HZ10000⟧ omega ⟦HZ12345⟧ end"
    assert find_sentinels(masked) == {"⟦HZ10000⟧", "⟦HZ12345⟧"}
    assert restore(masked, {"⟦HZ10000⟧": "A", "⟦HZ12345⟧": "B"}) == "alpha A omega B end"


def test_roundtrip_input_containing_literal_5digit_sentinel():
    # A literal 5-digit sentinel already in the INPUT must be locked and survive verbatim.
    _roundtrip("Keep this exact token ⟦HZ10000⟧ intact through the rewrite.")
