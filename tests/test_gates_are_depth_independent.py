"""Every meaning gate must give the same verdict wherever in the document the edit sits.

Two of them did not, and the reason was the same 256-token truncation in both cases:
`contradiction_score` (fixed earlier by chunking) and `entailment_score` (fixed by chunking it
too, once the difflib aligner made that safe). This file is the standing version of the probe that
found both — the property no test suite naturally checks, applied to all five gates rather than to
whichever one is currently suspect.

The padding is WHOLE SENTENCES on purpose. A first version built it with
`" ".join((filler * 40).split()[:n])`, which cuts mid-sentence and glues the probe onto the
fragment — "The report covers procurement, staffing, The regulator sued the company" — so spaCy
parses one run-on sentence and `role_swap` flips non-monotonically with `n`. That looked exactly
like a depth bug in `roles.py` and was an artefact of the fixture. With well-formed padding the
gate is stable at every depth from 0 to 288 words.
"""

from __future__ import annotations

import pytest

from untell.scripts.entailment import available as nli_available
from untell.scripts.entailment import meaning_preserved
from untell.scripts.hedges import certainty_kept, polarity_kept
from untell.scripts.numerals import numbers_kept
from untell.scripts.quality import similarity
from untell.scripts.roles import available as roles_available
from untell.scripts.roles import role_swap

# One complete sentence, repeated. Never truncated.
_PAD = "The report covers procurement and staffing across regional offices. "
_DEPTHS = [0, 1, 2, 4, 8, 16, 32]


def _at(depth: int, tail: str) -> str:
    return _PAD * depth + tail


# Deletion is the one gate property with a MEASURED depth limit, so its depths are listed
# separately rather than shared with the others. Chunking moved the blind spot from "anything past
# ~130 words" to "a deletion diluted inside its own ~80-word chunk"; see the note in
# `entailment_score`. 174 words is inside the verified range, 318 is not.
_LOSS_DEPTHS = [0, 1, 2, 4, 8, 16]

_DELETED_CLAUSE = (
    "The trial enrolled patients from rural clinics across the northern districts, ran under "
    "close supervision by an external board, and reported its findings to the regional health "
    "authority before publication."
)


@pytest.mark.parametrize("depth", _LOSS_DEPTHS, ids=lambda d: f"{d * 9}w")
def test_meaning_loss_is_caught_at_any_depth(depth: int) -> None:
    """Deletion contradicts nothing, so only the entailment half can catch it.

    Before entailment was chunked this failed from 140 words on, unconditionally, at 0.9800.
    """
    if not nli_available():
        pytest.skip("NLI unavailable")
    src = _at(depth, _DELETED_CLAUSE)
    cut = _at(depth, "The trial ran.")
    assert not meaning_preserved(src, cut, similarity(src, cut), 0.76)


def test_the_deletion_limit_is_where_it_was_measured() -> None:
    """Pins the KNOWN failure so it is a documented boundary rather than a surprise.

    At 318 words the text splits into four ~80-word chunks and the deletion occupies a third of
    one, so the model reads that chunk as largely entailed. If a future change fixes this, the test
    fails and the note in `entailment_score` needs updating with it.
    """
    if not nli_available():
        pytest.skip("NLI unavailable")
    src = _at(32, _DELETED_CLAUSE)
    cut = _at(32, "The trial ran.")
    assert len(src.split()) > 300
    assert meaning_preserved(src, cut, similarity(src, cut), 0.76), (
        "the 318-word deletion is now caught — good, but update the limit recorded in "
        "entailment_score and in this test"
    )


@pytest.mark.parametrize("depth", _DEPTHS, ids=lambda d: f"{d * 9}w")
def test_meaning_inversion_is_caught_at_any_depth(depth: int) -> None:
    if not nli_available():
        pytest.skip("NLI unavailable")
    src = _at(depth, "The treatment improved outcomes for the patients.")
    bad = _at(depth, "The treatment did not improve outcomes for the patients.")
    assert not meaning_preserved(src, bad, similarity(src, bad), 0.76)


@pytest.mark.parametrize("depth", _DEPTHS, ids=lambda d: f"{d * 9}w")
def test_role_swap_is_caught_at_any_depth(depth: int) -> None:
    if not roles_available():
        pytest.skip("spaCy model unavailable")
    a = _at(depth, "The regulator sued the company over the disclosure.")
    b = _at(depth, "The company sued the regulator over the disclosure.")
    assert role_swap(a, b) is True


@pytest.mark.parametrize("depth", _DEPTHS, ids=lambda d: f"{d * 9}w")
def test_the_lexical_gates_are_depth_independent(depth: int) -> None:
    """These are regex-based and cannot truncate — asserted so a rewrite of them cannot regress."""
    assert not numbers_kept(
        _at(depth, "The trial enrolled 1,250 patients across five sites."),
        _at(depth, "The trial enrolled patients across sites."),
    )
    assert not certainty_kept(
        _at(depth, "The drug may reduce mortality in some patients."),
        _at(depth, "The drug reduces mortality in patients."),
    )
    assert not polarity_kept(
        _at(depth, "The committee approved the plan."),
        _at(depth, "The committee did not approve the plan."),
    )


@pytest.mark.parametrize("depth", _DEPTHS, ids=lambda d: f"{d * 9}w")
def test_a_faithful_rewrite_passes_at_any_depth(depth: int) -> None:
    """The other direction: a gate that rejects everything is depth-independent and useless."""
    if not nli_available():
        pytest.skip("NLI unavailable")
    src = _at(depth, "The committee approved the plan on Tuesday after a long review.")
    ok = _at(depth, "On Tuesday, after a long review, the committee approved the plan.")
    assert meaning_preserved(src, ok, similarity(src, ok), 0.76)
