"""Preserve-lock round-trip tests."""

from __future__ import annotations

import json

import pytest

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


def test_percent_and_degree_units_are_locked_whole():
    """A trailing \b after the unit could only match when the symbol was followed by a word char,
    which never happens in prose. So "5%" locked NOTHING and "42%" locked only the digits."""
    from untell.scripts.preserve import lock

    for text, expected in [
        ("The error rate was 5%.", "5%"),
        ("The model achieved 42% accuracy.", "42%"),
        ("It rose to 30\u00b0.", "30\u00b0"),
        ("Temperature hit 30\u00b0C today.", "30\u00b0C"),
    ]:
        _masked, mapping = lock(text)
        assert expected in mapping.values(), f"{expected!r} not locked in {text!r}: {mapping}"


def test_percent_sign_cannot_be_rewritten_away_while_sentinel_survives():
    """The exploit the old pattern allowed: lock only the digits, leave "%" as raw text, and a
    rewrite turning "<sentinel>%" into "<sentinel> percent" passes the sentinel integrity check
    while silently changing the number's unit."""
    import re

    from untell.scripts.preserve import lock, restore

    masked, mapping = lock("The model achieved 42% accuracy.")
    sentinels = re.findall(r"\u27e6HZ\d{4,}\u27e7", masked)
    assert sentinels, "nothing was locked"
    # With the whole "42%" locked, the "%" is inside the sentinel and cannot be reached.
    assert "%" not in masked
    assert restore(masked, mapping) == "The model achieved 42% accuracy."


# --------------------------------------------------------------------------- lock COVERAGE
# The round-trip test (restore(*lock(t)) == t) cannot detect a coverage gap: unlocked text passes
# through unchanged, so the identity holds whether or not a fact is protected. That is exactly how
# "5%" shipped locked-as-nothing. These assert the OTHER property — the fact is really inside a
# sentinel — and specifically guard against PARTIAL locking, where a sentinel appears and the span
# looks protected while the rest of the fact stays mutable.
COVERAGE_CASES = [
    ("percent 1-digit", "The error rate was 5%.", "5%"),
    ("percent 2-digit", "Accuracy hit 42% overall.", "42%"),
    ("percent decimal", "It grew 3.5% last year.", "3.5%"),
    ("degree bare", "It rose to 30\u00b0.", "30\u00b0"),
    ("degree C", "Temperature hit 30\u00b0C today.", "30\u00b0C"),
    ("currency", "It cost $5 to make.", "$5"),
    ("currency large", "Revenue was $1,200,000 last year.", "$1,200,000"),
    ("decimal", "Pi is roughly 3.14 in most uses.", "3.14"),
    ("thousands", "About 1,000 people showed up.", "1,000"),
    ("year", "It launched in 2020 to acclaim.", "2020"),
    ("unit kg", "The load was 10kg total.", "10kg"),
    ("unit spaced", "We waited 5 days for it.", "5 days"),
    ("citation bracket", "Prior work showed this [12].", "[12]"),
    ("citation author", "As shown by Smith (2020), it holds.", "Smith (2020)"),
    ("url", "See https://example.com/paper for more.", "https://example.com/paper"),
    ("quote", 'She said "this is the key finding" clearly.', '"this is the key finding"'),
    ("ratio", "The split was 3:1 in favour.", "3:1"),
    ("range", "Between 10-20 people attended.", "10-20"),
    ("fraction", "About 2/3 of them agreed.", "2/3"),
    ("time", "It started at 9:30 sharp.", "9:30"),
    ("date iso", "Recorded on 2024-03-15 exactly.", "2024-03-15"),
    ("version", "Upgrade to v2.1.3 now.", "v2.1.3"),
    ("negative", "It fell by -15 points.", "-15"),
    ("scientific", "Around 1.5e10 particles.", "1.5e10"),
    ("email", "Contact a@b.com for access.", "a@b.com"),
    ("p-value", "Significant at p<0.05 level.", "p<0.05"),
]


@pytest.mark.parametrize("desc,text,must_survive", COVERAGE_CASES)
def test_fact_is_locked_whole_not_partially(desc, text, must_survive):
    from untell.scripts.preserve import lock

    _masked, mapping = lock(text)
    values = list(mapping.values())
    assert any(must_survive == v or must_survive in v for v in values), (
        f"{desc}: {must_survive!r} not locked whole in {text!r}; locked={values!r}"
    )


def test_sign_and_operator_cannot_be_stripped_from_a_locked_number():
    """The two most dangerous partial locks: a dropped minus sign flips a number's sign, and a
    freed comparison operator inverts a statistical claim ("p<0.05" -> "p>0.05")."""
    from untell.scripts.preserve import lock

    masked, _ = lock("It fell by -15 points and was significant at p<0.05 level.")
    assert "-15" not in masked  # the sign is inside the sentinel
    assert "<" not in masked  # so is the operator
