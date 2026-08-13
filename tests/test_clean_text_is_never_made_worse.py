"""On text with nothing wrong with it, an edit has to buy something.

A user runs this on their own clean writing — no catalogued tells, a score already low. The tool
still rewrites. That is defensible only if the rewrite helps, and the interesting case is the one
where it does not: an edit that raises the detector score has replaced the user's wording and made
the number worse.

MEASURED over 5 clean texts (0 tells each) at 24 seeds, counting only draws that changed the text,
and recording per draw rather than as a mean:

    rewriter      texts regressing   worst delta   tells added
    structural         3 of 5          +0.1010          0
    composite          0 of 5           0.0000          0

Structural alone can make clean text worse — once on the informal passage (+0.0522), once on a lone
sentence (+0.1010), twice on the recollection (+0.0305). Composite never does, across all 120
draws, because its internal best-of-N discards the draws that would.

That is the same mechanism the composite docstring now credits for the whole margin over a single
structural call, seen from the other side: selection is not just where the gain comes from, it is
what stops the losses. This file pins the property a caller depends on — the DEFAULT rewriter does
not degrade text it had no complaint about.
"""

from __future__ import annotations

import random

import pytest

from untell.rewriter import get_rewriter
from untell.scripts.score import score_text
from untell.scripts.tells import score_tells

CLEAN = {
    "academic":
        "The study examined soil carbon at eleven sites over four years, sampling to ninety "
        "centimetres. Mean stocks were 82.4 t/ha in the deepest layer, against 41.7 at the surface.",
    "informal":
        "My grandmother kept every birthday card anyone ever sent her, in a shoebox, in date "
        "order. When she died we found forty years of them. Half were from people none of us could "
        "place.",
    "technical":
        "Implementations must reject frames whose declared length exceeds the negotiated maximum. "
        "A receiver that encounters an unknown opcode terminates the connection with status 1003.",
    "one sentence": "An unsupervised segmentation approach was used throughout the study.",
    "recollection":
        "The oven has been dead since March. I keep meaning to call someone about it and then I "
        "do not. The toaster oven does most of what I need, so roast chicken is off the menu.",
}
SEEDS = range(24)
# Detector noise. A hair either way is not a regression; +0.05 and +0.10 are.
_EPS = 0.01


@pytest.fixture(autouse=True)
def stdlib_lite(monkeypatch):
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")


def _regressions(rewriter: str, text: str) -> list[float]:
    """Score deltas for draws that CHANGED the text and made the score worse."""
    baseline = score_text(text, tier="lite")["max"]
    rw = get_rewriter(rewriter)
    scored = score_text(text, tier="lite")
    out = []
    for seed in SEEDS:
        random.seed(seed)
        candidate = rw.rewrite(text, scored, 0.30)
        if candidate.strip() == text.strip():
            continue
        delta = score_text(candidate, tier="lite")["max"] - baseline
        if delta > _EPS:
            out.append(delta)
    return out


@pytest.mark.parametrize("name", sorted(CLEAN))
def test_the_fixture_is_actually_clean(name: str) -> None:
    """The premise. On text that already has tells, "do not make it worse" is a different claim."""
    assert score_tells(CLEAN[name])["tells"] == 0, f"{name} is no longer a clean fixture"


@pytest.mark.parametrize("name", sorted(CLEAN))
def test_the_default_rewriter_never_makes_clean_text_worse(name: str) -> None:
    regressions = _regressions("composite", CLEAN[name])
    assert not regressions, (
        f"composite raised the detector score on {name} in {len(regressions)} of {len(SEEDS)} "
        f"draws (worst {max(regressions):+.4f}) — the selector is no longer discarding the draws "
        f"that make clean text worse"
    )


@pytest.mark.parametrize("name", sorted(CLEAN))
def test_the_default_rewriter_never_adds_a_tell_to_clean_text(name: str) -> None:
    text = CLEAN[name]
    rw = get_rewriter("composite")
    scored = score_text(text, tier="lite")
    for seed in SEEDS:
        random.seed(seed)
        candidate = rw.rewrite(text, scored, 0.30)
        added = score_tells(candidate)["tells"]
        assert added == 0, (
            f"composite introduced {added} tell(s) into clean {name} at seed {seed}: {candidate!r}"
        )


def test_an_unselected_rewriter_does_regress_somewhere() -> None:
    """Guards every case above. If NOTHING ever regressed these fixtures, "composite never
    regresses" would be true of any implementation, including one that does nothing at all. The
    claim only means something because structural alone demonstrably can."""
    regressing = {
        name: _regressions("structural", text)
        for name, text in CLEAN.items()
    }
    total = sum(len(v) for v in regressing.values())
    assert total > 0, (
        "structural regressed none of these fixtures at any seed, so the composite assertions "
        "above are vacuous — find a fixture where an unselected draw can lose"
    )
