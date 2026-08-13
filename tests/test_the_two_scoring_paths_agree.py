"""Per-sentence targeting and the rewrite loop score through different functions.

`score_sentences` reaches the detectors through `batch_score_texts`; `untell_text` and every verdict
surface reach them through `score_text`. Nothing required the two to agree, and a drift between them
would put the sentences the rewriter is told to fix on a different scale from the verdict it is
judged by — the targeting would be pointing at a document nobody is scoring.

MEASURED over 12 HC3 texts, both halves, at `tier=lite`:

    worst |max| difference      0.000000
    keys in one and not other   none

Exact agreement. Pinned here because it holds by accident: the two functions share `_score_with_detectors`
today, and nothing says they must. Result 209 records the cost of leaving that kind of property
unwritten — the non-redundancy of eleven caveats turned out to rest on a wording change made three
results earlier for an unrelated reason, which nobody had recorded as a requirement.

Deliberately not asserting a specific value. The point is that the two paths answer alike, whatever
they answer, so this stays true across detector changes, threshold changes and corpus changes.
"""

from __future__ import annotations

import logging

import pytest

from untell.scripts.score import batch_score_texts, score_text

TEXTS = [
    "Salt lowers the freezing point of water, which is why councils spread it on roads in winter. "
    "It works down to about minus nine degrees, below which other chemicals are needed instead.",
    "Moreover, the framework leverages a robust approach to delivery at scale across the whole "
    "programme. Furthermore, it is important to note that this underscores the pivotal integration.",
    "The trial met its primary endpoint at every recruiting site, but the safety profile that "
    "emerged during follow-up raised concerns among the independent reviewers who examined it.",
]


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


@pytest.mark.parametrize("text", TEXTS, ids=["plain", "tell heavy", "contrastive"])
def test_the_two_paths_return_the_same_max(text: str) -> None:
    single = score_text(text, tier="lite")
    batched = batch_score_texts([text], tier="lite")[0]
    assert single["max"] == pytest.approx(batched["max"], abs=1e-9)


@pytest.mark.parametrize("text", TEXTS, ids=["plain", "tell heavy", "contrastive"])
def test_the_two_paths_return_the_same_keys(text: str) -> None:
    """A field present on one path and not the other is the same defect one level up: a caller
    reading `flagged` from the batch path would get a KeyError the single path never produces."""
    single = set(score_text(text, tier="lite"))
    batched = set(batch_score_texts([text], tier="lite")[0])
    assert single == batched, {"only single": sorted(single - batched),
                               "only batch": sorted(batched - single)}


@pytest.mark.parametrize("text", TEXTS, ids=["plain", "tell heavy", "contrastive"])
def test_the_two_paths_agree_per_detector(text: str) -> None:
    """Stronger than `max`, and the one that would catch a reordering: `max` can match while the
    members behind it differ."""
    single = score_text(text, tier="lite").get("detectors") or {}
    batched = batch_score_texts([text], tier="lite")[0].get("detectors") or {}
    assert set(single) == set(batched)
    for name, value in single.items():
        if isinstance(value, (int, float)):
            assert value == pytest.approx(batched[name], abs=1e-9), name


def test_a_batch_of_several_matches_one_at_a_time() -> None:
    """The batch path exists to load detectors once for many texts, so the risk it carries is state
    leaking between items — a score that depends on what was scored before it."""
    together = batch_score_texts(TEXTS, tier="lite")
    apart = [batch_score_texts([t], tier="lite")[0] for t in TEXTS]
    for index, (a, b) in enumerate(zip(together, apart)):
        assert a["max"] == pytest.approx(b["max"], abs=1e-9), index


def test_the_scores_are_not_all_identical() -> None:
    """Guards the guard. Three texts scoring the same number would satisfy every assertion above
    while proving nothing — the shape of a saturating detector, which this repo has shipped."""
    values = {score_text(t, tier="lite")["max"] for t in TEXTS}
    assert len(values) > 1, values
