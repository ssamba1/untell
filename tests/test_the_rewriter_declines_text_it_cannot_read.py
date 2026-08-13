"""The rewriter welded English words into German and French.

Every transform in `structural_rewrite` is English. Applied to Latin-script text that is not
English they do not fail — they produce fluent-looking damage. MEASURED end to end at default
settings, every word the loop changed:

    Die Studie ...        ->  Of course, die Studie ...
    ... erheblich. Die    ->  ... erheblich, and die
    ... sur le site. Les  ->  ... sur le site, and les

An opener from the pool, and `and` as a clause joiner. Two transforms, two different English words,
which is why the gate is on the pipeline rather than on either one — fixing only the opener would
have left the joiner, and the joiner is the one I did not notice first.

The existing language guard could not catch it. `_language_supported` compares Latin to non-Latin
characters, so it separates Chinese from German and German is Latin. On the Chinese control it
fires correctly and the loop leaves the text alone; German sailed through with no caveat at all.

WHY THE OBVIOUS TEST DOES NOT WORK. The share of English function words alone does not separate the
classes: a run of English headings scores 0.000 and Italian scores 0.125. Any single bar either
lets German through or disables the rewriter on English headings, and the second is far worse — it
would silence the tool on text it can read. So the check requires POSITIVE evidence of another
language: enough other-language function words, and more of them than English ones. MEASURED over
10 deliberately awkward English samples and 6 non-English:

    floor   English false positives   non-English caught
    0.10            0/10                     6/6
    0.12            0/10                     6/6
    0.15            0/10                     5/6   (Portuguese, 0.136)

0.12 has margin on both sides. The "more than English" half does the real work: the sample full of
French and German proper nouns scores 0.130 on other-language words and is NOT flagged, because its
English share is 0.261.

Returning the input unchanged is the honest outcome — the tool cannot rewrite what it cannot read,
and unchanged text beats damaged text.
"""

from __future__ import annotations

import pytest

from untell.rewriter.structural import structural_rewrite
from untell.scripts.run import untell_text
from untell.scripts.tells import looks_non_english

NON_ENGLISH = {
    "spanish": "El estudio examinó el carbono del suelo en once sitios durante cuatro años. "
               "Los resultados variaron según la profundidad de la muestra tomada en cada sitio.",
    "german": "Die Studie untersuchte den Kohlenstoffgehalt des Bodens an elf Standorten. "
              "Die Ergebnisse variierten je nach Tiefe der entnommenen Bodenprobe erheblich.",
    "french": "L'étude a examiné le carbone du sol sur onze sites pendant quatre années entières. "
              "Les résultats variaient selon la profondeur de l'échantillon prélevé sur le site.",
    "italian": "Lo studio ha esaminato il carbonio del suolo in undici siti per quattro anni. "
               "I risultati variavano a seconda della profondità del campione prelevato.",
    "portuguese": "O estudo examinou o carbono do solo em onze locais durante quatro anos. "
                  "Os resultados variaram conforme a profundidade da amostra recolhida.",
    "dutch": "De studie onderzocht het koolstofgehalte van de bodem op elf locaties. "
             "De resultaten varieerden afhankelijk van de diepte van het genomen monster.",
}

# Deliberately awkward English: the shapes with the fewest function words, plus two that carry
# other-language vocabulary without being in another language.
ENGLISH = {
    "informal": "My grandmother kept every birthday card anyone ever sent her, in a shoebox, in "
                "date order. When she died we found forty years of them in the wardrobe.",
    "AI-formal": "Moreover, the framework leverages a robust approach to deliver transformative "
                 "outcomes for every stakeholder involved in the wider programme of work.",
    "academic": "The study examined soil carbon at eleven sites over four years, sampling to "
                "ninety centimetres, and reported mean stocks of 82.4 t/ha in the deepest layer.",
    "technical spec": "Implementations must reject frames whose declared length exceeds the "
                      "negotiated maximum. A receiver encountering an unknown opcode terminates "
                      "the connection with status 1003.",
    "terse list": "Install dependencies. Run migrations. Restart workers. Verify health endpoint. "
                  "Check logs for errors. Roll back on failure now.",
    "code-heavy prose": "Call untell.score first, then untell.tells; pass --tier lite and read "
                        "verdict_threshold from config.yaml before invoking run() at all.",
    "english quoting german": "The paper uses the term Kohlenstoffgehalt throughout, which the "
                              "authors gloss as carbon content, and it is the standard usage.",
    "proper nouns": "Angela Merkel met Jacques Chirac in Strasbourg. Le Monde covered it. "
                    "Der Spiegel ran a longer piece the following week about the summit.",
}


@pytest.mark.parametrize("name", sorted(ENGLISH))
def test_english_is_never_mistaken_for_another_language(name: str) -> None:
    """The error that matters most. A false positive silences the rewriter on text it can read."""
    assert not looks_non_english(ENGLISH[name])


@pytest.mark.parametrize("name", sorted(NON_ENGLISH))
def test_other_latin_script_languages_are_recognised(name: str) -> None:
    assert looks_non_english(NON_ENGLISH[name])


@pytest.mark.parametrize("name", sorted(NON_ENGLISH))
def test_the_structural_rewriter_returns_such_text_unchanged(name: str) -> None:
    text = NON_ENGLISH[name]
    for seed in range(6):
        assert structural_rewrite(text, intensity=0.7, seed=seed) == text


# Which English samples the rewriter actually changes, MEASURED over 8 seeds each:
#
#     AI-formal 8/8   informal 8/8   code-heavy prose 8/8   english quoting german 8/8
#     technical spec 6/8   academic 1/8   proper nouns 0/8   terse list 0/8
#
# The two zeros are not the language gate — `looks_non_english` is False for both, asserted above.
# They are samples with nothing the pipeline transforms: a run of names and a run of imperatives,
# chosen for this file because they have the FEWEST function words and so sit nearest the decision
# boundary. That makes them good gate fixtures and useless rewrite fixtures. Asserting per sample
# would have pinned a property of the fixture rather than of the gate.
_REWRITTEN_IN_PRACTICE = frozenset(
    {"AI-formal", "informal", "code-heavy prose", "english quoting german", "technical spec"}
)


@pytest.mark.parametrize("name", sorted(_REWRITTEN_IN_PRACTICE))
def test_english_is_still_rewritten(name: str) -> None:
    """Guards the guard. A gate that declined everything would pass every test above."""
    text = ENGLISH[name]
    assert any(structural_rewrite(text, intensity=0.7, seed=s) != text for s in range(8)), (
        f"the {name} sample is no longer rewritten at any seed; the language gate is over-reaching"
    )


def test_the_boundary_samples_are_ungated_even_though_they_are_not_rewritten() -> None:
    """The two samples the check above excludes still have to pass the gate, and they are the ones
    most likely to fail it — a run of French and German proper nouns, and a list with almost no
    function words at all. Excluding them from the rewrite check must not excuse them here."""
    for name in ("proper nouns", "terse list"):
        assert not looks_non_english(ENGLISH[name]), name


@pytest.mark.parametrize("name", ["german", "french"])
def test_no_english_word_is_welded_into_the_output_end_to_end(name: str, monkeypatch) -> None:
    """Through the whole loop, not just the transform — the composite path reaches surgical too."""
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
    text = NON_ENGLISH[name]
    result = untell_text(text, tier="lite", rewriter="composite", threshold=0.001)

    added = set(result["final"].split()) - set(text.split())
    assert not added, f"the loop introduced {sorted(added)} into {name} text"
