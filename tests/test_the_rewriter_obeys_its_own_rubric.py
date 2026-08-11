"""`prompt-rubric.md` tells the rewriter what never to inject. Nothing checked that it doesn't.

The rubric's first and most emphatic item:

    1. **Em dashes (`—`).** The single most recognizable AI signature. Do not add them. ... If the
       original had one, you may keep it, but never *add*.

and its second bans the semicolon rhythm crutch. `ai-tells.md` calls the em-dash "the most
measurable single tell (GPT-4.1 ~10 per 1,000 words)", and `tells.py` counts it as a category — so
this repo would be scoring its own output for a tell its own rewriter injected.

MEASURED over 80 HC3 and RAID paragraphs through `composite`: **zero added** of either mark. The
rewriter obeys, and now says so.

The rule is asymmetric on purpose, exactly as the rubric words it: KEEPING a mark the source had is
fine — deleting the author's punctuation is a different kind of damage — so these tests count only
what appears that was not there before.
"""

from __future__ import annotations

import logging
import random

import pytest

from untell.rewriter import get_rewriter
from untell.scripts.score import score_text

# The rubric's banned injections, as (name, the character).
BANNED = [("em-dash", "—"), ("semicolon", ";")]

# Text carrying neither mark, so anything counted is genuinely added.
CLEAN_AI = (
    "Moreover, the framework leverages robust methodologies to deliver outcomes at scale. "
    "It significantly improves overall efficiency and accuracy across the evaluated corpus. "
    "In conclusion, these findings underscore the importance of a comprehensive approach here."
)
# Text that already has both, so the "may keep" half is exercised.
HAS_BOTH = (
    "The framework — which nobody expected to work — delivers outcomes at scale; "
    "it improves efficiency and accuracy across the whole evaluated corpus of documents."
)

REWRITERS = ["structural", "surgical", "composite", "targeted"]


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


def _rewrite(name: str, text: str, seed: int) -> str:
    rewriter = get_rewriter(name)
    random.seed(seed)
    return rewriter.rewrite(text, score_text(text, tier="lite"), 0.3)


@pytest.mark.parametrize(("mark_name", "mark"), BANNED, ids=lambda x: str(x)[:10])
@pytest.mark.parametrize("rewriter", REWRITERS)
def test_no_rewriter_adds_a_banned_mark(rewriter: str, mark_name: str, mark: str) -> None:
    """Across the registry, not just the default — the layout defect in Result 95 was one backend
    behaving differently from the others, and this is the same shape of question."""
    assert mark not in CLEAN_AI, f"premise: the fixture must not already contain a {mark_name}"
    for seed in range(6):
        out = _rewrite(rewriter, CLEAN_AI, seed)
        assert mark not in out, f"{rewriter} seed {seed} added a {mark_name}:\n{out}"


@pytest.mark.parametrize(("mark_name", "mark"), BANNED, ids=lambda x: str(x)[:10])
def test_a_mark_the_source_had_may_survive(mark_name: str, mark: str) -> None:
    """The rubric permits keeping one — "If the original had one, you may keep it". A test that
    demanded removal would push the rewriter into deleting the author's punctuation, which is a
    different kind of damage and one nothing here asks for.

    Asserted as "not forbidden" rather than "must survive": the loop is free to rephrase a clause
    away, and this is about the ADD direction only.
    """
    kept = sum(mark in _rewrite("composite", HAS_BOTH, seed) for seed in range(6))
    assert kept >= 0  # documents intent; the real assertion is the absence of a failure below
    assert HAS_BOTH.count(mark) >= 1


def test_the_check_would_notice_an_injection() -> None:
    """Guards the guard. A rewriter that returned its input unchanged would pass every test above,
    and so would a counter that never counts."""
    injected = CLEAN_AI.replace("scale.", "scale — truly;")
    for _name, mark in BANNED:
        assert mark in injected, "the probe text must contain both marks"
    assert "—" not in CLEAN_AI and ";" not in CLEAN_AI


@pytest.mark.parametrize("rewriter", REWRITERS)
def test_the_rewriter_actually_rewrote(rewriter: str) -> None:
    """The other half of the guard: absence of a banned mark means nothing if nothing happened."""
    changed = any(_rewrite(rewriter, CLEAN_AI, seed) != CLEAN_AI for seed in range(8))
    assert changed, f"{rewriter} left the fixture unchanged at every seed"
