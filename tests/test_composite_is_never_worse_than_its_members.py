"""Composite claims to beat both members. Check the claim a caller actually relies on.

Its docstring used to say structural and surgical "combined are far more effective than either
alone, at no cost". Half right, wrong attribution. Mean detector max over 10 seeds, one call each:

    text              before   surgical   structural   composite
    ai vocab heavy    0.664     0.607       0.332        0.294
    delve tapestry    0.511     0.485       0.358        0.284
    hedged report     0.533     0.482       0.284        0.123
    plain academic    0.565     0.565       0.202        0.195

Composite beats surgical everywhere, and beats a single structural call everywhere. But the margin
is NOT the chaining. Replacing the surgical stage with an identity function inside the class — same
seeds, same draws — leaves the output byte-identical 10/10 on three texts, scores equal to four
decimals. The gain is the internal best-of-N selection; surgical acts on AI vocabulary structural
has already removed, and changed nothing in 0 of 60 draws across five texts.

What this file pins is the property a caller depends on and that a refactor could plausibly break:
composite is never WORSE than either member. Not the inert stage — a test asserting surgical stays
inert would fail the day someone improves it, which would be a good change badly punished.
"""

from __future__ import annotations

import random
import statistics

import pytest

from untell.rewriter import get_rewriter
from untell.scripts.score import score_text

TEXTS = {
    "ai vocab heavy":
        "Moreover, the framework leverages robust methodologies to deliver outcomes at scale. "
        "It significantly improves overall efficiency and accuracy across the evaluated corpus. "
        "In conclusion, these findings underscore the importance of a comprehensive approach here.",
    "delve tapestry":
        "We delve into the rich tapestry of this realm to leverage robust systems. "
        "The multifaceted landscape underscores a pivotal paradigm for every stakeholder involved. "
        "Ultimately, the groundbreaking approach showcases seamless integration at considerable scale.",
    "hedged report":
        "It is important to note that the results may potentially indicate a possible trend. "
        "Furthermore, additional research could arguably help clarify these preliminary findings. "
        "In essence, the comprehensive analysis underscores the pivotal need for further study.",
}
SEEDS = range(8)
# The tie band. Composite selects among random draws, so "never worse" is a claim about the mean,
# not about every draw, and a hair of noise must not fail it.
_EPS = 0.02


@pytest.fixture(autouse=True)
def stdlib_lite(monkeypatch):
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")


def _mean_score(rewriter: str, text: str) -> float:
    rw = get_rewriter(rewriter)
    scored = score_text(text, tier="lite")
    out = []
    for seed in SEEDS:
        random.seed(seed)
        out.append(score_text(rw.rewrite(text, scored, 0.30), tier="lite")["max"])
    return statistics.mean(out)


@pytest.mark.parametrize("name", sorted(TEXTS))
@pytest.mark.parametrize("member", ["surgical", "structural"])
def test_composite_is_not_worse_than_the_member(name: str, member: str) -> None:
    text = TEXTS[name]
    composite = _mean_score("composite", text)
    alone = _mean_score(member, text)
    assert composite <= alone + _EPS, (
        f"on {name}, composite scores {composite:.4f} against {member} alone at {alone:.4f} — "
        f"the chain is doing worse than one of its own members"
    )


@pytest.mark.parametrize("name", sorted(TEXTS))
def test_every_rewriter_actually_lowers_the_score(name: str) -> None:
    """Guards the guard. If no rewriter moved the score, "composite is not worse" would hold
    trivially and this file would be asserting nothing about anything."""
    text = TEXTS[name]
    before = score_text(text, tier="lite")["max"]
    after = _mean_score("composite", text)
    assert after < before - 0.05, (
        f"composite barely moves {name}: {before:.4f} -> {after:.4f}; the comparison above is "
        f"between two numbers that mean nothing"
    )


def test_the_members_are_genuinely_different_rewriters() -> None:
    """Second guard. If `get_rewriter` returned the same object for both names, every comparison
    above would be a value against itself."""
    surgical, structural = get_rewriter("surgical"), get_rewriter("structural")
    assert type(surgical) is not type(structural)

    text = TEXTS["ai vocab heavy"]
    scored = score_text(text, tier="lite")
    random.seed(0)
    a = surgical.rewrite(text, scored, 0.30)
    random.seed(0)
    b = structural.rewrite(text, scored, 0.30)
    assert a != b, "surgical and structural produced the same output; they are not distinct here"
