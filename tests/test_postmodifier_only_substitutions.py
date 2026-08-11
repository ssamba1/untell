""""a lot" is a noun phrase. It can follow what it modifies, and premodify only a comparative.

FOUND in the `--json` output of the humanize CLI, which is where a caller reads the actual text:

    It significantly improves overall efficiency   ->   It A LOT IMPROVES overall efficiency

MEASURED across 240 HC3 and RAID texts, 67 of the 68 `significantly` occurrences are followed by a
word — so the broken slot is the usual one, not the exception.

The exception that keeps this from being a blanket rule is the comparative. "significantly longer"
-> "a lot longer" is correct English, and so are "a lot better" and "a lot more". A noun-phrase
adverbial may premodify a comparative and nothing else, which is a rule about the following word
rather than about its part of speech, so it needs no parser.
"""

from __future__ import annotations

import random

import pytest

from untell.attacks.word_importance import _SYN
from untell.rewriter.structural import (
    _POSTMODIFIER_ONLY,
    _plain_register,
    _premodifies_a_comparative,
)

DRAWS = 40


def _outputs(text: str) -> set[str]:
    out = set()
    for seed in range(DRAWS):
        random.seed(seed)
        out.add(_plain_register(text, intensity=1.0))
    return out


PREMODIFYING_A_VERB = [
    "It significantly improves overall efficiency and accuracy across the corpus.",
    "The treatment significantly suppressed the inflammatory response in every trial.",
]

LEGITIMATE = [
    "The wait was significantly longer than anyone had expected that year.",
    "The result was significantly better than the previous published baseline.",
    "Performance improved significantly, which the reviewers noted in their report.",
]


@pytest.mark.parametrize("text", PREMODIFYING_A_VERB, ids=lambda t: t[:30])
def test_a_noun_phrase_never_premodifies_a_verb(text: str) -> None:
    for out in _outputs(text):
        assert "a lot improve" not in out and "a lot suppress" not in out, out


@pytest.mark.parametrize("text", PREMODIFYING_A_VERB, ids=lambda t: t[:30])
def test_the_other_substitutes_still_fire_there(text: str) -> None:
    """Guards the guard. Declining the swap outright would satisfy the test above and leave
    `significantly` — an AI-vocabulary word the table exists to flatten — in place."""
    changed = _outputs(text) - {text}
    assert changed, "the swap was declined rather than filtered"
    assert all("significantly" not in c for c in changed)


@pytest.mark.parametrize("text", LEGITIMATE, ids=lambda t: t[:30])
def test_the_slots_where_it_is_correct_still_use_it(text: str) -> None:
    """Before a comparative and after the verb, "a lot" is the most natural of the three. Removing
    it from the table would cost exactly those."""
    assert any("a lot" in out for out in _outputs(text)), text


@pytest.mark.parametrize(
    ("following", "ok"),
    [
        (["longer"], True),
        (["better"], True),
        (["more", "robust"], True),
        (["fewer"], True),
        (["improves"], False),
        (["suppressed"], False),
        (["difficult"], False),
        (["her"], False),   # short -er word that is not a comparative
        ([], False),
    ],
    ids=lambda x: str(x)[:20],
)
def test_the_comparative_test_itself(following: list[str], ok: bool) -> None:
    assert _premodifies_a_comparative(following) is ok


# A noun-phrase adverbial opens with a determiner or a quantifier and has more than one word.
_NOUN_PHRASE_LEAD = frozenset({"a", "an", "the", "all", "no", "some", "every", "one", "plenty"})


def _noun_phrase_substitutes(head: str) -> list[str]:
    return [
        s for s in _SYN.get(head, [])
        if " " in s and s.split()[0].lower() in _NOUN_PHRASE_LEAD
    ]


ADVERBS_AT_RISK = sorted(
    head for head in _SYN if head.endswith("ly") and _noun_phrase_substitutes(head)
)


def test_the_scan_finds_something() -> None:
    """Guards the guard below: a broken extraction makes it pass over an empty list."""
    assert "significantly" in ADVERBS_AT_RISK, "the headword this rule came from is not in the scan"


@pytest.mark.parametrize("head", ADVERBS_AT_RISK)
def test_every_adverb_with_a_noun_phrase_substitute_is_guarded(head: str) -> None:
    """The category, not the instance. Scanning the table found exactly one -ly headword offering a
    noun-phrase substitute; a new entry offering another would reopen the defect silently."""
    guarded = {s.lower() for s in _POSTMODIFIER_ONLY.get(head, frozenset())}
    assert set(_noun_phrase_substitutes(head)) <= guarded, (
        f"{head!r} can emit {_noun_phrase_substitutes(head)} in front of a verb. A noun-phrase "
        "adverbial premodifies nothing but a comparative — add it to _POSTMODIFIER_ONLY."
    )


def test_the_map_names_a_real_substitute() -> None:
    """An entry naming a word the table no longer offers reads as protection and is not — the check
    that caught a phantom `involved` key in `_GERUND_UNSAFE` on the hour it was written."""
    for head, unsafe in _POSTMODIFIER_ONLY.items():
        assert head in _SYN, f"{head!r} is guarded but no longer in _SYN"
        listed = {s.lower() for s in _SYN[head]}
        assert unsafe & listed, f"none of {sorted(unsafe)} substitutes {head!r} any more"
        assert listed - unsafe, f"every substitute for {head!r} is restricted; drop the headword"
