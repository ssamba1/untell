"""Three ways `dominant_script` could be wrong today with every test green.

Round ninety-four mutation-tested the package and enumerated 49 surviving mutants — single-token
edits to shipped code that no test notices. A survivor list is only worth the acting on, and a list
nobody acts on is the same defect rounds ninety-one and ninety-two kept finding: work recorded and
then not done. These three survivors are in `untell/languages.py`:

    line 112  counts[name] = counts.get(name, 0) + 1   ->  - 1
    line 116  counts["Latin"] = counts.get("Latin", 0) + 1  ->  - 1
    line 126  max(counts.items(), ...)  ->  min(...)

The third is the one that matters. The function is called `dominant_script` and its docstring says
"an English paragraph quoting one Chinese phrase stays Latin" — and **nothing tested that it picks
the majority script over a minority one.** Swapping `max` for `min` inverted the entire purpose of
the function and the suite stayed green.

The first two are the counters underneath it: with `- 1` every tally runs negative, which `min` and
`max` then read in whichever order the mutation leaves. Each is asserted separately so a single test
does not stand in for three distinct failures.

Why this matters beyond the function: `dominant_script` decides `catalogue_for`, which decides which
tell catalogue a document is scored against. A text routed to the wrong catalogue is scored by the
wrong rules, and the docstring already notes the constraint that it must agree with
`_language_supported` "or a text could be called unsupported and then routed nowhere".
"""

from __future__ import annotations

import pytest

from untell.languages import catalogue_for, dominant_script

LATIN = "The quick brown fox jumps over the lazy dog and keeps on running through the field."
CYRILLIC = "Быстрая коричневая лиса прыгает через ленивую собаку и продолжает бежать по полю."
HAN = "敏捷的棕色狐狸跳过懒惰的狗并继续在田野里奔跑而且一直不停下来直到天黑为止真的很快"


def test_a_paragraph_quoting_one_foreign_phrase_keeps_its_own_script():
    """The docstring's own example, which nothing checked."""
    assert dominant_script(LATIN + " 你好世界") == "Latin"


def test_the_majority_script_wins_not_the_minority_one():
    """Kills `max -> min` at line 126. Without this the function returns the RAREST script."""
    mixed = LATIN * 3 + CYRILLIC[:20]
    assert dominant_script(mixed) == "Latin"

    other = CYRILLIC * 3 + LATIN[:20]
    assert dominant_script(other) == "Cyrillic"


def test_the_answer_flips_when_the_balance_flips():
    """A single-direction test passes under `min` whenever the expected script is also the rarest.

    So both directions are asserted on the SAME pair of scripts: no substitution of `min` for `max`
    can satisfy both at once.
    """
    latin_heavy = LATIN * 4 + CYRILLIC[:15]
    cyrillic_heavy = CYRILLIC * 4 + LATIN[:15]
    assert dominant_script(latin_heavy) != dominant_script(cyrillic_heavy)
    assert dominant_script(latin_heavy) == "Latin"
    assert dominant_script(cyrillic_heavy) == "Cyrillic"


@pytest.mark.parametrize("text,script", [
    (LATIN, "Latin"),
    (CYRILLIC, "Cyrillic"),
    (HAN, "Han"),
])
def test_a_single_script_document_reports_that_script(text: str, script: str):
    assert dominant_script(text) == script


def test_counting_is_monotone_in_the_number_of_characters():
    """Kills `+ 1 -> - 1` at lines 112 and 116, which a single-script test cannot.

    With a decrementing counter every tally is negative and one script still wins, so the answer for
    a pure document is unchanged. What changes is the ORDERING between two scripts as one of them
    grows, which is what this asserts.
    """
    # MEASURED: LATIN carries 67 letters and CYRILLIC 69, so one copy of each already tips
    # Cyrillic. The assertion is on the ORDERING as one side grows, not on a guessed crossover.
    for extra in (1, 2, 4, 8):
        assert dominant_script(CYRILLIC * extra + LATIN) == "Cyrillic", extra
    for extra in (2, 4, 8):
        assert dominant_script(LATIN * extra + CYRILLIC) == "Latin", extra


def test_a_document_with_no_letters_at_all_falls_back_rather_than_raising():
    assert dominant_script("") == "Latin"
    assert dominant_script("123 456 !!! ...") == "Latin"


def test_the_script_decides_which_catalogue_scores_the_document():
    """Why the above is not a cosmetic detail: it routes the document."""
    assert catalogue_for(LATIN) is not None
    assert catalogue_for(LATIN + " 你好") is catalogue_for(LATIN)
