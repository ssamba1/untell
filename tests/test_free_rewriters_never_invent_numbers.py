"""`numbers_kept` is one-directional on purpose, and the reason is a measurement that can rot.

An invented number — "Several sites joined." -> "12 sites joined." — is a meaning change and is
deliberately NOT vetoed. The justification in `numerals.numbers_kept` is that the free rewriters
cannot produce a digit at all (0 of 80 runs), so the veto would never fire where it can be checked,
while firing often on the hosted-LLM path where "half the cohort" -> "50% of the cohort" is faithful.

That argument is only as good as its zero. Re-measured against the current rewriters over 40 real
HC3 texts at 2 seeds: still 0 invented and 0 dropped, 80 of 80. This file keeps a corpus-free
version of that check running, so the day a rewriter learns to emit a digit, the decision gets
revisited instead of silently becoming wrong.

Deliberately covers all four local rewriters, not just composite: the measurement was taken on
composite, and "no path generates a digit" is a claim about the free rewriters as a class.
"""

from __future__ import annotations

import random
import re

import pytest

from untell.rewriter import get_rewriter
from untell.scripts.numerals import missing_numbers
from untell.scripts.preserve import lock, restore
from untell.scripts.tells import score_tells

_DIGITS = re.compile(r"\d+")

# Vague quantifiers are the bait: these are exactly the phrases an LLM renders as a numeral, so if
# any local rewriter had such a path this is the text that would trip it.
_PROSE = [
    "Several sites joined the trial last year, and a couple of them dropped out after a few weeks. "
    "Most of the cohort stayed on, though the rate roughly doubled over the following months.",
    "Moreover, numerous participants reported that the effect was substantial. Furthermore, a "
    "handful of the sites observed that outcomes improved dramatically across the board.",
    "The team leveraged robust methodologies to deliver seamless outcomes at scale, and many of "
    "the stakeholders noted that the results were a testament to the evolving landscape.",
    "Dozens of researchers examined the question over the past decade, and the majority concluded "
    "that the association held. A minority disagreed, citing the small size of the early studies.",
]

_REWRITERS = ["composite", "structural", "surgical", "targeted"]


def _rewrite(rw, text: str) -> str | None:
    masked, mapping = lock(text)
    try:
        candidate = rw.rewrite(masked, score_tells(masked), 0.3)
    except TypeError:
        candidate = rw.rewrite(masked, score_tells(masked))
    except Exception:
        return None
    return restore(candidate, mapping)


@pytest.mark.parametrize("name", _REWRITERS)
def test_no_free_rewriter_invents_a_digit(name: str) -> None:
    rw = get_rewriter(prefer=name)
    if rw is None or not rw.available():
        pytest.skip(f"{name} unavailable")
    ran = 0
    for text in _PROSE:
        for seed in range(3):
            random.seed(seed)
            out = _rewrite(rw, text)
            if out is None:
                continue
            ran += 1
            new = set(_DIGITS.findall(out)) - set(_DIGITS.findall(text))
            assert not new, (
                f"{name} invented {sorted(new)} from prose with no digits — `numbers_kept` is "
                f"one-directional on the measured assumption that this cannot happen:\n{out}"
            )
    assert ran, f"{name} produced no candidates; this proved nothing"


@pytest.mark.parametrize("name", _REWRITERS)
def test_no_free_rewriter_drops_a_number(name: str) -> None:
    """The direction that IS vetoed, checked at the source so the veto is not the only line."""
    rw = get_rewriter(prefer=name)
    if rw is None or not rw.available():
        pytest.skip(f"{name} unavailable")
    text = (
        "The trial ran for 12 weeks across 5 sites and enrolled 1,250 people, of whom 97 percent "
        "completed every visit. Smith (2020) reported the result and Jones (2021) confirmed it."
    )
    ran = 0
    for seed in range(3):
        random.seed(seed)
        out = _rewrite(rw, text)
        if out is None:
            continue
        ran += 1
        assert not missing_numbers(text, out), f"{name} dropped a number:\n{out}"
    assert ran, f"{name} produced no candidates; this proved nothing"
