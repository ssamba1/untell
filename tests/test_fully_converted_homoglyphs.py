"""A word converted entirely to homoglyphs mixes nothing, so the mixed-script check could not see it.

`_homoglyph_warning` flagged words containing BOTH Latin and Cyrillic/Greek letters — the signature
of a partial substitution. A word where every letter was replaced has no Latin left:

    "саре"   c, a, p, e all Cyrillic, renders as "cape"   ->   no warning

That word carries exactly the risk the warning exists for. The score is unaffected because the
detectors normalise confusables, but the substitution is still in the text and another tool may not.

The signal is CONFUSABILITY, not script. Flagging any non-Latin word would fire on a Russian
quotation inside an English document, which is ordinary multilingual text. A converted word is one
whose every letter has an ASCII lookalike, tested against `unicode_tricks._UNHOMOGLYPH` — the
scrubber's own map, so the detector and the remedy cannot disagree about what a confusable is.
Genuine Cyrillic contains letters with no Latin twin (п, и, в) and does not match.
"""

from __future__ import annotations

import pytest

from untell.attacks.unicode_tricks import _HOMOGLYPH, _UNHOMOGLYPH
from untell.scripts.score import _homoglyph_warning, _is_all_confusable, score_text

ENGLISH = "The cape was fine and the rest of this sentence is ordinary English prose."


def _convert(word: str) -> str:
    """The word with every letter replaced by its Cyrillic lookalike."""
    return "".join(_HOMOGLYPH.get(c, c) for c in word)


def test_a_fully_converted_word_is_reported() -> None:
    converted = _convert("cape")
    assert converted != "cape", "premise: every letter must have a homoglyph"
    warning = _homoglyph_warning(ENGLISH.replace("cape", converted))
    assert warning and "entirely" in warning, warning
    assert "untell scrub" in warning


def test_a_partly_converted_word_is_still_reported() -> None:
    """Guards the guard: the original mixed-script case must keep working."""
    warning = _homoglyph_warning(ENGLISH.replace("cape", "c" + _HOMOGLYPH["a"] + "pe"))
    assert warning and "mix" in warning, warning


def test_plain_english_is_not_reported() -> None:
    assert _homoglyph_warning(ENGLISH) is None


@pytest.mark.parametrize(
    ("language", "text"),
    [
        ("Russian", "The report said привет which is a greeting and nothing more."),
        ("Greek", "The letter λογος appears in the appendix of the published paper."),
        ("Bulgarian", "The sign читалище marks the community reading room in the village."),
    ],
    ids=lambda x: str(x)[:12],
)
def test_a_real_foreign_word_is_not_an_attack(language: str, text: str) -> None:
    """The false positive this rule is shaped to avoid. Multilingual text is not homoglyph
    substitution, and a warning telling someone to `untell scrub` their Russian would be wrong."""
    assert _homoglyph_warning(text) is None, language


@pytest.mark.parametrize(
    "word",
    [
        "cape",     # every letter has a homoglyph -> fully converted
        "apex",     # same
        "space",    # 's' has none -> partly converted, must land in the MIXED branch
        "core",     # 'r' has none -> same
        "escape",   # 's' has none -> same
        "rhythm",   # no letter has one -> unchanged, must warn about nothing
    ],
)
def test_whatever_the_attack_emits_the_warning_can_see(word: str) -> None:
    """One branch or the other, for every word the emit map can touch.

    The first version of this asserted `_is_all_confusable` on all of them and failed on three —
    correctly. "space" cannot be fully converted because `s` has no homoglyph in the emit map, so it
    comes out mixed, which is the case the ORIGINAL branch was written for. The invariant worth
    asserting is not that every word converts fully; it is that nothing the attack produces escapes
    both branches.
    """
    converted = _convert(word)
    text = ENGLISH.replace("cape", converted)
    if converted == word:
        assert _homoglyph_warning(text) is None, f"{word!r} was not altered; nothing to warn about"
        return
    fully = _is_all_confusable(converted)
    warning = _homoglyph_warning(text)
    assert warning, f"{converted!r} escaped both branches"
    assert ("entirely" in warning) is fully, (converted, fully, warning)


def test_the_two_maps_agree() -> None:
    """`_is_all_confusable` reads `_UNHOMOGLYPH`; the attack writes `_HOMOGLYPH`. Anything the
    attack can emit must be in the map the check reads, or a substitution this repo performs is
    invisible to this repo's own warning."""
    unseen = sorted(v for v in _HOMOGLYPH.values() if v not in _UNHOMOGLYPH)
    assert not unseen, f"emitted homoglyphs the scrub map does not know: {unseen}"


def test_it_reaches_the_scored_result() -> None:
    """The warning is only useful where a caller reads it."""
    text = " ".join([ENGLISH.replace("cape", _convert("cape"))] * 3)
    warning = score_text(text, tier="lite").get("warning") or ""
    assert "entirely" in warning or "mix" in warning, warning
