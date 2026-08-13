"""`--style academic` still opened sentences with "Basically,".

The formal profiles already decline contractions and hold back the plain-word swap, on the stated
ground that "utilize" -> "use" is the right move for casual prose and the wrong one for a paper. The
opener pool is the same argument and was never covered by it. The rate dial worked — academic is
0.4x, technical 0.3x — but the VOCABULARY was identical at every style.

MEASURED over 60 rewrites of one paper abstract, openers emitted, before:

    none          Actually 2  Also 1  In short 2  In practice 3  Basically 1  Of course 2
    academic      Actually 2          In practice 2  Basically 1  Of course 2
    technical     Actually 1          In practice 1               Of course 2
    professional  Actually 2  In short 1  In practice 2  Basically 1  Of course 2

and after:

    academic      In practice 3  Now 3  Of course 1
    technical     In practice 1  Now 2  Of course 1
    professional  In practice 3  Now 3  Of course 2

FOUND while measuring something else — whether a second pass over the tool's own output drifts. It
does not (pass 2 is byte-identical on three documents at default seeding, so the loop converges),
but one of the outputs read "Actually, the study examined soil carbon at 11 sites over 4 years",
which is a register error no metric in the repo can see: the tell catalogue scores it 0.
"""

from __future__ import annotations

import collections
import random

import pytest

from untell.rewriter.structural import (
    _CONVERSATIONAL_OPENERS,
    _OPENERS,
    structural_rewrite,
    style_profile,
)

PAPER = (
    "The study examined soil carbon at eleven sites over four years, sampling to ninety centimetres. "
    "Mean stocks were 82.4 t/ha in the deepest layer, against 41.7 t/ha at the surface. "
    "Prior work reported 78.9 t/ha using the same protocol at three of the sites. "
    "The discrepancy is attributable to differences in bulk-density correction across surveys."
)
FORMAL_STYLES = ["academic", "professional", "technical"]
SEEDS = range(60)


def _openers_emitted(style: str | None) -> collections.Counter:
    found: collections.Counter = collections.Counter()
    for seed in SEEDS:
        random.seed(seed)
        out = structural_rewrite(PAPER, intensity=0.7, style=style)
        for opener in _OPENERS:
            if out.lstrip().startswith(opener) or f" {opener} " in f" {out} ":
                found[opener] += 1
    return found


def test_the_conversational_set_is_a_subset_of_the_pool() -> None:
    """A typo here would silently disable the filter rather than fail anything."""
    assert _CONVERSATIONAL_OPENERS
    assert _CONVERSATIONAL_OPENERS <= set(_OPENERS), (
        f"not in the pool, so filtering them does nothing: "
        f"{_CONVERSATIONAL_OPENERS - set(_OPENERS)}"
    )


@pytest.mark.parametrize("style", FORMAL_STYLES)
def test_a_formal_style_never_emits_a_conversational_opener(style: str) -> None:
    emitted = _openers_emitted(style)
    offenders = {o: n for o, n in emitted.items() if o in _CONVERSATIONAL_OPENERS}
    assert not offenders, f"--style {style} emitted spoken-register openers: {offenders}"


@pytest.mark.parametrize("style", FORMAL_STYLES)
def test_a_formal_style_still_gets_openers(style: str) -> None:
    """Guards the guard. Steering the pool must not silence the transform — a style that emitted
    nothing would pass the test above, and the transform exists to break repeated openers."""
    emitted = _openers_emitted(style)
    assert sum(emitted.values()) > 0, (
        f"--style {style} emitted no opener at all across {len(SEEDS)} seeds; the filter is "
        f"silencing the transform rather than steering it"
    )


def test_the_default_style_keeps_the_whole_pool() -> None:
    """The restriction is a property of formal profiles, not a global narrowing. Casual prose is
    where these openers were measured as human in the first place."""
    assert style_profile(None)["conversational_openers"] is True
    for style in ("casual", "conversational", "storytelling"):
        assert style_profile(style)["conversational_openers"] is True, style


@pytest.mark.parametrize("style", FORMAL_STYLES)
def test_the_formal_profiles_declare_the_restriction(style: str) -> None:
    assert style_profile(style)["conversational_openers"] is False


def test_an_unknown_style_is_not_treated_as_formal() -> None:
    """`style_profile` falls back to the neutral default for anything it does not know, and the
    neutral default is the previous behaviour. A silent narrowing on a typo'd style name would be
    the wrong direction to fail in."""
    assert style_profile("acedemic")["conversational_openers"] is True
