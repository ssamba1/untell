"""Every number in the result is checked against the text it claims to describe.

FOUND by generalising Result 176. `flagged_sentences` was stale by construction and unreadable when
it was not stale; the obvious next question is whether any other reported figure describes something
other than what the caller received.

MEASURED on 8 HC3 documents, 4 of which the loop changed, each field against a fresh computation:

    post.max      vs score_text(final)["max"]     0/8 disagree
    tells_after   vs score_tells(final)["tells"]  0/8 disagree
    pre.max       vs score_text(input)["max"]     0/8 disagree
    tells_before  vs score_tells(input)["tells"]  0/8 disagree

Four of five clean. The fifth was not.

`similarity` compared `masked` against `best_masked` whenever polish had not run — masked text on
both sides. The justification in the code was that `best_masked` restores to `final`, so the
comparison is exact. That is true of the TEXT and false of the NUMBER: a sentinel is one token
standing in for a multi-word span, so both sides share a cheap exact match exactly where the real
words would have had to be compared.

MEASURED, reported value minus a fresh `similarity(input, final)`, over documents the loop changed:

    plain             6 changed   mean +0.0013   worst +0.0040   reported higher 3/6
    citation-dense    7 changed   mean +0.0040   worst +0.0155   reported higher 5/7

**One-directional** — never below — and it grows with how much of the document is locked, which is
the population that most needs a trustworthy meaning number. After the change both arms report
exactly the caller's own figure: mean and worst gap 0.000000, on the same 6 and 7 documents.

The gate's own masked comparison is a separate decision, measured and deliberately kept. This file is
about the number a caller reads.
"""

from __future__ import annotations

import logging

import pytest

from untell.scripts.quality import similarity
from untell.scripts.run import untell_text
from untell.scripts.score import score_text
from untell.scripts.tells import score_tells

PLAIN = (
    "Moreover, the framework leverages a robust approach to delivery at scale across the whole "
    "programme. Furthermore, it is important to note that this underscores the pivotal integration "
    "for every team. The system utilizes a comprehensive methodology throughout the year. "
    "Additionally, the platform empowers users to streamline their daily workflows considerably. "
    "In conclusion, organizations must harness these seamless solutions today."
)
# Locked spans on most sentences: this is the arm where a masked comparison flatters the result.
DENSE = (
    "Moreover, the framework leverages a robust approach [1] (see https://example.com/a, 12 March "
    "2019) to delivery at scale. Furthermore, this underscores the pivotal integration for every "
    "team. The system utilizes a comprehensive methodology [2] (see https://example.com/b, 4 June "
    "2020) throughout the year. Additionally, the platform empowers users to streamline workflows. "
    "In conclusion, organizations must harness these seamless solutions [3] today."
)
KWARGS = dict(tier="lite", threshold=0.3, max_iters=2, rewriter="structural", best_of=1, seed=3)


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


@pytest.fixture(scope="module")
def runs() -> dict[str, tuple[str, dict]]:
    return {name: (text, untell_text(text, **KWARGS)) for name, text in
            (("plain", PLAIN), ("dense", DENSE))}


def test_the_loop_changed_at_least_one_document(runs) -> None:
    """The denominator. An untouched document makes every assertion below trivially true: `final`
    is the input, so every figure about one is a figure about the other."""
    assert any(result.get("changed") for _text, result in runs.values()), (
        "nothing was rewritten; no reported number was at risk of describing a different text"
    )


@pytest.mark.parametrize("name", ["plain", "dense"])
def test_similarity_is_the_number_the_caller_can_reproduce(name: str, runs) -> None:
    """The defect. Computed on masked text it was systematically high — never low — by up to
    +0.0155 on citation-dense input, because a sentinel matches a sentinel for free."""
    text, result = runs[name]
    assert result.get("similarity") == pytest.approx(
        similarity(text, result.get("final") or ""), abs=1e-9
    )


@pytest.mark.parametrize("name", ["plain", "dense"])
def test_post_describes_the_final_text(name: str, runs) -> None:
    text, result = runs[name]
    fresh = score_text(result.get("final") or "", tier="lite")
    assert result["post"]["max"] == pytest.approx(fresh["max"], abs=5e-4)


@pytest.mark.parametrize("name", ["plain", "dense"])
def test_pre_describes_the_input(name: str, runs) -> None:
    text, result = runs[name]
    assert result["pre"]["max"] == pytest.approx(score_text(text, tier="lite")["max"], abs=5e-4)


@pytest.mark.parametrize("name", ["plain", "dense"])
def test_the_tell_counts_describe_their_own_ends(name: str, runs) -> None:
    text, result = runs[name]
    assert result.get("tells_before") == score_tells(text)["tells"]
    assert result.get("tells_after") == score_tells(result.get("final") or "")["tells"]


def test_a_masked_comparison_really_would_have_been_higher() -> None:
    """Guards the guard, and pins the mechanism rather than the symptom. If masking stopped
    inflating similarity, the assertions above would still pass and this measurement would have
    quietly stopped meaning anything."""
    from untell.scripts.preserve import lock

    masked, mapping = lock(DENSE)
    assert mapping, "nothing was locked; this text cannot show the effect"
    # Same edit applied to both forms: drop a word that is not inside a locked span.
    edited_plain = DENSE.replace("comprehensive ", "", 1)
    edited_masked, _ = lock(edited_plain)
    assert similarity(masked, edited_masked) >= similarity(DENSE, edited_plain)
