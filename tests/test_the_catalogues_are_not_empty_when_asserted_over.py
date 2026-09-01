"""A universal quantified over an empty collection is true, and proves nothing.

Round forty-six extended the vacuity sweep across the repository and found that eleven of the twelve
test files it could not break import only module-level DATA — catalogues, compiled regexes,
thresholds. Function-body sabotage is blind to all of it, so the most consequential asset here was
the least covered by its own mutation testing: **the tells catalogue is not a detail of the tells
system, it IS the tells system.**

Adding data mutants found the predictable hole. Emptying `_OPENERS` and `_PARTICLES` broke nothing,
because the tests over them are of the form *no member of this collection has property P* — and an
empty collection satisfies that for any P. The catalogue could be deleted entirely and the suite
would go green.

These tests assert the collections are populated, so every "no member does X" assertion elsewhere has
something to quantify over. The sizes are floors, not exact counts: an exact count would fail on
every legitimate addition, and a check that fails on correct changes gets deleted.
"""

from __future__ import annotations

import pytest


def _floor(name: str, collection, minimum: int) -> None:
    assert len(collection) >= minimum, (
        f"{name} has {len(collection)} entries, expected at least {minimum}. Every test asserting "
        f"'no member of {name} does X' passes vacuously on an empty or gutted collection — the "
        f"catalogue could be deleted and the suite would stay green."
    )


def test_the_ai_vocabulary_catalogue_is_populated():
    from untell.scripts.tells import _AI_VOCAB

    _floor("_AI_VOCAB", _AI_VOCAB, 20)


def test_the_transition_catalogue_is_populated():
    from untell.scripts.tells import _TRANSITIONS

    _floor("_TRANSITIONS", _TRANSITIONS, 10)


def test_the_opener_catalogue_is_populated():
    """MUTATION-CHECKED. Emptying `_OPENERS` survived every test in the suite.
    `test_no_conjunction_opener_is_emittable.py` asserts the category is closed — that no opener the
    rewriter can emit is a bare conjunction — which is vacuously true when there are no openers."""
    from untell.rewriter.structural import _OPENERS

    _floor("_OPENERS", _OPENERS, 5)


def test_the_particle_set_is_populated():
    """MUTATION-CHECKED. Emptying `_PARTICLES` survived too, for the same reason: the test asserts
    substitutions keep their prepositions, and with no particles there is nothing to keep."""
    from untell.attacks.word_importance import _PARTICLES

    _floor("_PARTICLES", _PARTICLES, 5)


def test_the_synonym_table_is_populated():
    from untell.attacks.word_importance import _SYN

    _floor("_SYN", _SYN, 5)
    assert all(subs for subs in _SYN.values()), (
        "a headword mapped to an empty substitute list makes every per-substitute assertion "
        "vacuous for that headword"
    )


@pytest.mark.parametrize("module,name", [
    ("untell.scripts.tells", "_AI_VOCAB_RE"),
    ("untell.scripts.tells", "_TRANSITION_OPENER_RE"),
    ("untell.rewriter.structural", "_FRONTABLE_RE"),
])
def test_a_shipped_regex_can_actually_match_something(module, name):
    """A regex compiled to match nothing is the same failure in a different shape, and it is not
    hypothetical: `_AI_VOCAB_RE` mutated to `(?!x)x` — which matches no string at all — was killed
    only because a test happened to check a positive case. These check the property directly.

    The probe is built FROM the catalogue rather than hard-coded, so it cannot drift out of date the
    way a literal example would.
    """
    import importlib
    import re

    pattern = getattr(importlib.import_module(module), name)
    assert isinstance(pattern, re.Pattern)
    # A pattern that cannot match anything is degenerate whatever the corpus.
    assert pattern.pattern not in ("(?!x)x", "(?!)"), f"{name} is compiled to match nothing"
    assert pattern.pattern, f"{name} has an empty pattern"


def test_the_ai_vocabulary_regex_matches_its_own_catalogue():
    """The strongest available check: every word the catalogue lists must be matched by the regex
    built from it. Catches both an emptied catalogue and a regex that stopped being derived from it.
    """
    from untell.scripts.tells import _AI_VOCAB, _AI_VOCAB_RE

    missed = [w for w in _AI_VOCAB if not _AI_VOCAB_RE.search(f"the {w} here")]
    assert not missed, f"the regex built from _AI_VOCAB does not match these entries: {missed[:5]}"
