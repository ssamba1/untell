"""lock() must protect the same spans in NFC and NFD — normalization is not content.

A fact written with precomposed characters ("García, 2020") and the same fact
written decomposed ("Garcia\u0301a, 2020") are the same fact. MEASURED before the
fix, they were protected differently:

    lock("(García, 2020)")          ->  locks 'García' + '2020'  (name via NER only)
    lock("(Garci\u0301a, 2020)")    ->  locks ONLY '2020'        (name free)

The name's protection depended on whether spaCy happened to tag the composed form
as a PERSON; the decomposed form was tagged by nothing, and the citation regex's
ASCII-only letter class matched neither. A rewrite could alter "García" while the
year's sentinel survived intact — the partial-lock worst case this file documents.

The citation letter class now admits Latin-1 supplement letters AND combining
marks, so the regex itself locks the name in both forms — normalization-independent
and NER-independent.
"""

from __future__ import annotations

import unicodedata

import pytest

from untell.scripts.preserve import lock

ACCENTED_NAMES = [
    "García", "Müller", "Zúñiga", "François", "Álvarez", "Sørensen",
    "Łódź", "Café", "Sánchez", "Núñez",
]


@pytest.mark.parametrize("name", ACCENTED_NAMES)
def test_a_parenthetical_citation_locks_the_same_in_nfc_and_nfd(name):
    nfc = f"({name}, 2020)"
    nfd = unicodedata.normalize("NFD", nfc)
    masked_nfc, map_nfc = lock(nfc)
    masked_nfd, map_nfd = lock(nfd)
    # Both forms must protect the author name — either the whole parenthetical
    # locks as one span, or the name does on its own. Compare in NFC so the
    # decomposed form's value matches the composed name.
    def name_locked(mapping) -> bool:
        return any(
            name in v or name in unicodedata.normalize("NFC", v)
            for v in mapping.values()
        )

    assert name_locked(map_nfc), f"NFC {name!r} not locked: {map_nfc!r}"
    assert name_locked(map_nfd), f"NFD {name!r} not locked: {map_nfd!r}"


@pytest.mark.parametrize("name", ACCENTED_NAMES)
def test_a_narrative_citation_locks_the_same_in_nfc_and_nfd(name):
    nfc = f"{name} (2020) showed that"
    nfd = unicodedata.normalize("NFD", nfc)
    _, map_nfc = lock(nfc)
    _, map_nfd = lock(nfd)

    def name_locked(mapping) -> bool:
        return any(
            name in v or name in unicodedata.normalize("NFC", v)
            for v in mapping.values()
        )

    assert name_locked(map_nfc), f"NFC narrative {name!r} not locked: {map_nfc!r}"
    assert name_locked(map_nfd), f"NFD narrative {name!r} not locked: {map_nfd!r}"


def test_et_al_keeps_the_accented_name_locked():
    nfc = "(Müller et al., 2021)"
    nfd = unicodedata.normalize("NFD", nfc)
    _, map_nfc = lock(nfc)
    _, map_nfd = lock(nfd)
    assert any("Müller" in v for v in map_nfc.values()), map_nfc
    assert any(
        "Müller" in unicodedata.normalize("NFC", v) for v in map_nfd.values()
    ), map_nfd


def test_round_trip_still_holds_for_both_forms():
    from untell.scripts.preserve import restore

    for text in ["(García, 2020)", unicodedata.normalize("NFD", "(García, 2020)")]:
        masked, mapping = lock(text)
        assert restore(masked, mapping) == text
