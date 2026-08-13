"""615 replacements, and not one of them is a catalogued tell.

This repository has shipped the opposite: fourteen replacements whose OUTPUT was itself in the tell
catalogue, so the swap moved a word from one flagged column to another and the total did not budge.
That was found and fixed in one table. `_SYN` is the other one — 226 source words, 615 replacement
strings, hand-maintained — and nothing had ever asked it the same question.

MEASURED, every replacement dropped into a carrier sentence that scores clean on its own:

    226 source words, 615 replacement strings
    replacements that are themselves catalogued ai_vocab     0
    replacements that introduce ANY catalogued category      0
    source words that ARE catalogued tells                   121 / 226

**No defect.** The last line is the one that makes the first two mean something: the map is pointed
the right way round, taking `delve`, `leverage`, `utilize`, `robust`, `seamless` and 116 others out
rather than in. A table that touched no tells at all would also score zero emissions and be useless.

The carrier is checked for cleanliness first. A carrier that already carried a tell would make every
replacement look guilty, and one that could not carry a tell at all would make every replacement look
innocent.
"""

from __future__ import annotations

import logging
from collections import Counter

import pytest

from untell.attacks.word_importance import _SYN
from untell.scripts.tells import _AI_VOCAB, score_tells

CARRIER = (
    "The team reviewed the plan and then {} the results before the meeting ended that "
    "afternoon, which gave everyone time to prepare their notes for the following week."
)

REPLACEMENTS = [
    (source, str(out))
    for source, outs in _SYN.items()
    for out in (outs if isinstance(outs, (list, tuple, set)) else [outs])
]


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


def test_the_carrier_is_clean_on_its_own() -> None:
    """Premise, and it fails in both directions. A carrier already carrying a tell makes every
    replacement look guilty; one that cannot carry a tell makes every replacement look innocent."""
    assert not (score_tells(CARRIER.format("checked")).get("by_category") or {})
    # A word from the catalogue in the exact form the catalogue lists. "delved into" was the first
    # attempt and scored clean: the vocabulary holds `delve`, matching is whole-word, and an
    # inflection is a different token. A positive control built from a near-miss proves nothing, and
    # this one caught its own author.
    assert (score_tells(CARRIER.format("leverage")).get("by_category") or {}), (
        "the carrier must be able to show a tell when one is present"
    )


def test_the_map_is_pointed_the_right_way_round() -> None:
    """More than half the SOURCE words are catalogued tells. Without this the zero below would be
    the score of a table that never touches a tell at all."""
    catalogued = {w.lower() for w in _AI_VOCAB}
    sources = [k for k in _SYN if k.lower() in catalogued]
    assert len(sources) > len(_SYN) // 3, f"{len(sources)}/{len(_SYN)}"


def test_no_replacement_is_itself_catalogued_vocabulary() -> None:
    catalogued = {w.lower() for w in _AI_VOCAB}
    offenders = [(s, o) for s, o in REPLACEMENTS if o.lower().strip() in catalogued]
    assert not offenders, offenders[:10]


def test_no_replacement_introduces_any_catalogued_category() -> None:
    """Wider than vocabulary: a replacement could be clean as a word and still complete a cliché,
    a formulaic transition or a participial trailer once it is in a sentence."""
    baseline = Counter(score_tells(CARRIER.format("checked")).get("by_category") or {})
    offenders = []
    for source, out in REPLACEMENTS:
        found = Counter(score_tells(CARRIER.format(out)).get("by_category") or {})
        extra = {c: v - baseline.get(c, 0) for c, v in found.items() if v > baseline.get(c, 0)}
        if extra:
            offenders.append((source, out, extra))
    assert not offenders, offenders[:10]
