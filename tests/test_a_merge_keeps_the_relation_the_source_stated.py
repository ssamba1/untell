"""Additive in, adversative out: 36% of merges asserted a relation the source contradicted.

FOUND by running the documented quickstart and reading the output, rather than the API. The CLI
returned:

    "Furthermore, it is important to note that this underscores the pivotal integration"
      ->  "..., but this highlights the critical integration"

`Furthermore` states that the second sentence ADDS to the first. `but` states that it opposes it.

`_MERGE_CONNECTORS` is `(", and ", ", but ", ", so ", ", while ", ", though ")`, chosen by weighted
random: three assert CONTRAST, one asserts CONSEQUENCE, and only `and` is relation-neutral.
`_vary_openers`, in the same file, screens "so", "then", "meanwhile" and "recently" out of its pool
on exactly this ground — each "asserts something about the sentence it is prepended to and the
meaning gates do not check discourse relations". The merger was inserting those relations at random.

MEASURED over 1000 merges of pairs whose second sentence opens with an explicit additive marker:

    , and 645    , but 224    , so 84    , while 40    , though 7

**355 of 1000 — 36% — contradict or invent a relation.** No gate can see it: no fact changed,
similarity stays high, and NLI reads two clauses that both still hold.

Two mechanisms were needed, and the first alone left an exact residual. `_strip_transitions` removes
the marker before `_merge_sentences` ever runs, so the relation has to be captured at strip time —
that took the stripped markers to 0/120 and left "In addition", "Also" and "Besides" at 37/120 each,
because `_TRANSITIONS_RE` does not strip those. Widening the stripper is not the fix: "Also," is an
opener `_vary_openers` deliberately ADDS on measured human frequency. Reading a surviving marker
directly closes it.

    after both        0 / 720 wrong-relation, across seven markers

Where the source states no relation there is nothing to honour, and the measured distribution stands:
`, and ` 135, `, but ` 42, `, so ` 18 over 200 seeds.
"""

from __future__ import annotations

import logging
import random
from collections import Counter

import pytest

import untell.rewriter.structural as structural
from untell.rewriter.structural import _merge_sentences, _strip_transitions, structural_rewrite

FIRST = "The system records every transaction in the ledger for later audit."
SECOND = "the platform notifies the finance team once the batch completes."
ADDITIVE = ["Furthermore,", "Additionally,", "Moreover,", "In addition,", "Also,", "Besides,"]
CONTRARY = {", but ", ", so ", ", while ", ", though "}
SEEDS = range(60)


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


def _merges(marker: str) -> list[str]:
    pair = [FIRST, f"{marker} {SECOND}"]
    captured: set[str] = set()
    stripped = _strip_transitions(pair, rate=1.0, additive_out=captured)
    out = []
    for seed in SEEDS:
        random.seed(seed)
        merged = _merge_sentences(list(stripped), rate=1.0, additive=captured)
        if len(merged) == 1:
            out.append(merged[0])
    return out


@pytest.mark.parametrize("marker", ADDITIVE)
def test_the_pair_actually_merges(marker: str) -> None:
    """The denominator. A pair the merger declines to join asserts no relation at all, and would
    satisfy the assertion below without the fix existing."""
    assert _merges(marker), f"{marker}: nothing merged; the connector was never chosen"


@pytest.mark.parametrize("marker", ADDITIVE)
def test_an_additive_source_never_becomes_a_contrast(marker: str) -> None:
    offenders = [m for m in _merges(marker) if any(c in m for c in CONTRARY)]
    assert not offenders, offenders[:2]


def test_both_mechanisms_are_load_bearing() -> None:
    """`Furthermore` is stripped before the merge and has to be captured; `Also` survives and has to
    be read in place. Either mechanism alone leaves the other marker at the random distribution."""
    captured: set[str] = set()
    _strip_transitions([FIRST, f"Furthermore, {SECOND}"], rate=1.0, additive_out=captured)
    assert captured, "the stripped marker was not captured"
    assert structural._opens_additive(f"Also, {SECOND}")
    assert not structural._opens_additive(f"However, {SECOND}")


def test_a_pair_with_no_stated_relation_keeps_its_variety() -> None:
    """Guards the guard. Forcing `, and ` everywhere would pass every assertion above and flatten a
    connector distribution that was measured against human writing."""
    seen: Counter = Counter()
    for seed in range(200):
        random.seed(seed)
        merged = _merge_sentences(
            ["The trial met its primary endpoint.",
             "The safety profile raised concerns among reviewers."],
            rate=1.0,
        )
        if len(merged) == 1:
            for connector in structural._MERGE_CONNECTORS:
                if connector in merged[0]:
                    seen[connector] += 1
                    break
    assert len(seen) >= 3, seen
    assert seen[", but "] > 0, seen


def test_the_case_from_the_cli_output() -> None:
    """The document that started this, through the shipped entry point at the seed that produced
    the adversative merge."""
    random.seed(3)
    out = structural_rewrite(
        "Moreover, the framework leverages a robust approach to delivery at scale across the "
        "programme. Furthermore, it is important to note that this underscores the pivotal "
        "integration for every team. The system utilizes a comprehensive methodology throughout "
        "the year."
    )
    assert ", but " not in out, out
