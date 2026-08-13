"""A fix whose output is itself a catalogued tell has shipped here before — fourteen times.

FOUND by reading real rewriter output rather than its metrics. A diff showed
`"It's important to note that the"` becoming `"Additionally, the"`, and `Additionally,` is a
catalogued `formulaic_transition` — apparently a cliché traded for a tell.

**It was not.** `Additionally` was in the SOURCE, and the rewriter removed it: over those six
documents `formulaic_transition` went **3 -> 0**. difflib had aligned a deletion in one place against
unrelated text elsewhere, and reading the diff without the source beside it produced a defect that
did not exist. The same misreading this log records at Result 114.

So the question became measurable instead. Every category, over 60 corpus texts, 60 real rewrites:

    DECREASES   repeated_phrasing -134   ai_vocab -55   formulaic_transition -31
                repeated_sentence_openers -28   cliche -11   hedge_stacking -4
                participial_trailer -2   negated_contrast -1

    INCREASES   repeated_sentence_openers +13   repeated_phrasing +2

Net-negative on every category, and only one emits at all: `_vary_openers` prepends markers, some of
which repeat, which is the known and budgeted cost of that transform — 13 against 28 removed.

**What this file covers and what it does not.** The synthetic set below runs in a second and asserts
the invariant that matters: no category comes out higher than it went in. It exercises `ai_vocab`,
`cliche` and `formulaic_transition` and does **not** reproduce the opener emission — that needs
corpus-length text, and the 60-text measurement above is the evidence for it. A green run here is not
a claim about `repeated_sentence_openers`.
"""

from __future__ import annotations

import logging
import random
from collections import Counter

import pytest

from untell.rewriter.structural import structural_rewrite
from untell.scripts.tells import score_tells

TELL_HEAVY = [
    "Moreover, the framework leverages a robust approach to deliver transformative outcomes at "
    "scale. Furthermore, it is important to note that this underscores the pivotal integration "
    "for teams. In conclusion, organizations must harness these seamless solutions today.",
    "It is worth noting that the system utilizes a comprehensive methodology. Additionally, the "
    "platform empowers users to streamline their workflows. Moreover, the intricate design "
    "fosters a vibrant ecosystem. Furthermore, stakeholders can leverage the myriad benefits.",
    "The approach is robust. The approach is scalable. The approach is comprehensive. The method "
    "delivers value. The method underscores impact. The method fosters growth in the landscape.",
]
SEEDS = (1, 5, 11)


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


@pytest.fixture(scope="module")
def deltas() -> tuple[Counter, Counter, int]:
    up: Counter = Counter()
    down: Counter = Counter()
    rewrites = 0
    for text in TELL_HEAVY:
        for seed in SEEDS:
            random.seed(seed)
            out = structural_rewrite(text)
            if out == text:
                continue
            rewrites += 1
            before = score_tells(text).get("by_category") or {}
            after = score_tells(out).get("by_category") or {}
            for category in set(before) | set(after):
                change = after.get(category, 0) - before.get(category, 0)
                if change > 0:
                    up[category] += change
                elif change < 0:
                    down[category] += -change
    return up, down, rewrites


def test_the_rewriter_actually_rewrote(deltas) -> None:
    """Premise. An untouched document emits nothing, and would satisfy every assertion below
    without the rewriter running at all — the trap this log has recorded twice."""
    _, _, rewrites = deltas
    assert rewrites >= len(TELL_HEAVY), rewrites


def test_no_category_comes_out_higher_than_it_went_in(deltas) -> None:
    """The invariant. A transform whose output is itself a catalogued tell trades one for another
    and the total does not move."""
    up, _, _ = deltas
    assert not up, dict(up)


def test_it_removes_more_than_it_leaves(deltas) -> None:
    """Guards the guard: a rewriter that changed nothing catalogued would satisfy the assertion
    above and be useless."""
    _, down, _ = deltas
    assert sum(down.values()) > 0, dict(down)


def test_the_categories_it_clears_are_the_ones_it_targets(deltas) -> None:
    """And they are the vocabulary transforms, not incidental collateral."""
    _, down, _ = deltas
    assert {"ai_vocab", "cliche", "formulaic_transition"} <= set(down), dict(down)


COMPONENTS = ("_flatten_cliches", "_strip_filler_openers", "_flatten_vague_attribution",
              "_flatten_copula", "_flatten_negated_contrast", "_flatten_participial_trailers")


@pytest.mark.parametrize("name", COMPONENTS)
def test_no_single_transform_emits_a_catalogued_tell(name: str) -> None:
    """Asserted per component, because the pipeline hides it.

    MEASURED: making `_flatten_cliches` substitute "Additionally, " for every deletion — the exact
    fourteen-times defect this file is named for — produces
    "Additionally, the method scales well..." from that function, and the FULL pipeline still scores
    `formulaic_transition` **0**, because a later transform strips catalogued transitions. Every
    output-level assertion above stays green.

    That is a real property of the pipeline rather than a hole in it: a user gets clean text either
    way. But it means the output contract cannot see a component regression, so the component is
    asserted directly. The guard-the-guard for the tests above failed for exactly this reason, and
    the failure was informative rather than a defect.
    """
    import untell.rewriter.structural as mod

    fn = getattr(mod, name)
    for text in TELL_HEAVY:
        out = fn(text)
        if out == text:
            continue
        before = (score_tells(text).get("by_category") or {})
        after = (score_tells(out).get("by_category") or {})
        emitted = {c: after[c] - before.get(c, 0) for c in after if after[c] > before.get(c, 0)}
        assert not emitted, f"{name} emitted {emitted}"
