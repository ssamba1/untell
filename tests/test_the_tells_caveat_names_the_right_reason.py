"""The caveat told a German reader their Latin-script paragraph was non-Latin.

`score_tells` refuses to pass off a zero from an inapplicable catalogue as a clean bill of health,
and says why. The reason was chosen two ways — has letters, or does not:

    has_letters   -> "the text is mostly non-Latin script"
    no letters    -> "the text contains no letters at all, so there is no prose to read"

A Latin-script language that is not English falls in the first branch and is described as
non-Latin. MEASURED on a four-sentence German paragraph: `tells` 0, `language_supported` False,
and the caveat read "this catalogue is English-only, and the text is mostly non-Latin script".

That is the exact failure the branch was written to prevent — its own comment says "saying the
wrong one sends the reader at the wrong fix". A reader told their German is non-Latin is sent
after an encoding problem they do not have, and the natural conclusion is that the warning is
broken, which costs the warning its credibility on the surface where it is the only signal.

`score`, `run` and the REST schema already say "a Latin-script language other than English" for
the same input, so this surface was also the one disagreeing with the other three. The split is
now three-way and uses `languages.dominant_script`, the same helper `_language_supported` routes
on, so the reason cannot drift from the decision.
"""

from __future__ import annotations

import pytest

from untell.scripts.tells import score_tells

GERMAN = (
    "Darüber hinaus ist es wichtig anzumerken, dass das umfassende Rahmenwerk robuste "
    "Methoden nutzt, um Mehrwert zu liefern. Abschließend stellt das System dar."
)
FRENCH = (
    "En outre, il est important de noter que le cadre complet utilise des méthodes "
    "robustes pour offrir de la valeur. En conclusion, le système représente cela."
)
CHINESE = "人工智能已经改变了许多行业和领域，并且继续快速发展着。"
RUSSIAN = "Это очень хорошая погода сегодня, и я хочу пойти гулять в парке."
SYMBOLS = "!!! ??? ... --- ### ;;; ,,,"
ENGLISH = (
    "Moreover, it is important to note that the comprehensive framework leverages "
    "robust methodologies to deliver value across the whole organisation today."
)

CASES = [
    ("german", GERMAN, "a Latin-script language other than English"),
    ("french", FRENCH, "a Latin-script language other than English"),
    ("chinese", CHINESE, "mostly non-Latin script"),
    ("russian", RUSSIAN, "mostly non-Latin script"),
    ("symbols", SYMBOLS, "no letters at all"),
]


@pytest.mark.parametrize("name,text,expected", CASES, ids=[c[0] for c in CASES])
def test_the_reason_describes_the_text(name: str, text: str, expected: str) -> None:
    result = score_tells(text)
    assert not result["language_supported"], f"{name}: fixture is stale, the catalogue applied"
    warning = str(result.get("warning") or "")
    assert expected in warning, f"{name}: expected {expected!r}, got {warning!r}"


@pytest.mark.parametrize("name,text", [("german", GERMAN), ("french", FRENCH)])
def test_a_latin_script_language_is_never_called_non_latin(name: str, text: str) -> None:
    """The specific false statement, asserted directly — an added third branch that still routed
    German down the old one would pass the test above only by accident of substring order."""
    warning = str(score_tells(text).get("warning") or "")
    assert "non-Latin" not in warning, f"{name}: {warning!r}"


def test_english_gets_no_language_caveat():
    """The other direction. A caveat on supported text would be worse than none."""
    result = score_tells(ENGLISH)
    assert result["language_supported"]
    assert "English-only" not in str(result.get("warning") or "")


def test_the_reason_agrees_with_the_surfaces_that_already_said_it():
    """`run` returns the same input unchanged with its own wording; the two must not disagree about
    what the text IS."""
    from untell.scripts.run import untell_text

    tells_warning = str(score_tells(GERMAN).get("warning") or "")
    run_warning = str(untell_text(GERMAN, tier="lite", max_iters=1).get("warning") or "")
    phrase = "Latin-script language other than English"
    assert phrase in tells_warning and phrase in run_warning, (
        f"tells={tells_warning[:120]!r}\nrun={run_warning[:120]!r}"
    )
