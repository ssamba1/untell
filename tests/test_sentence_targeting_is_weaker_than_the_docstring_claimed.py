"""Per-sentence targeting on the full tier is not the reliable half of the story it was recorded as.

`sentences.py` records "0.493 for the stdlib heuristic against 0.886-1.000 for every model-backed
detector", and `_targeting_is_uninformative` uses that split to decide when to warn a caller that
the ranking is arbitrary. Below the split, no warning.

Re-measured over 40 human and 40 AI HC3 sentences of 8+ words, each scored on its own:

    detector                AUROC    human mean    ai mean
    hc3_roberta             0.944       0.400        0.997
    perplexity_burstiness   0.831       0.083        0.275
    mage                    0.815       0.618        1.000
    roberta_openai          0.813       0.376        0.746
    fast_detectgpt          0.806       0.260        0.614
    ENSEMBLE max            0.813

Only `hc3_roberta` clears 0.886, and it is the detector trained on HC3. At the shipped 0.30 cut,
36 of 40 HUMAN sentences flag and 25 of 40 score at or above 0.99 — so on a deliberately mixed
document (a 7-sentence AI block inside 19 human sentences) targeting gave precision 0.444: five of
the nine spans handed to the rewriter were human writing.

These tests pin the CONSEQUENCE, not the AUROC. An exact 0.813 would break on any detector change,
while "human sentences saturate at the ceiling, so ranking them is not reliable" is the property
the warning decision rests on. They are marked slow: each loads the full ensemble.
"""
from __future__ import annotations

import pytest

from eval.datasets import load_pairs
from untell.scripts.score import batch_score_texts
from untell.text_split import split_sentences

MIN_WORDS = 8


@pytest.fixture(scope="module")
def sentences() -> dict:
    pairs = load_pairs("hc3", 30)
    if len(pairs) < 10:
        pytest.skip("needs the HC3 pairs")
    human, ai = [], []
    for h, a in pairs:
        human += [s.strip() for s in split_sentences(h) if len(s.split()) >= MIN_WORDS]
        ai += [s.strip() for s in split_sentences(a) if len(s.split()) >= MIN_WORDS]
    return {"human": human[:40], "ai": ai[:40]}


@pytest.fixture(scope="module")
def scored(sentences) -> dict:
    return {
        "human": [r["max"] for r in batch_score_texts(sentences["human"], tier="full")],
        "ai": [r["max"] for r in batch_score_texts(sentences["ai"], tier="full")],
    }


@pytest.mark.slow
def test_the_corpus_has_enough_sentences_to_measure(sentences):
    """Guards the guard: a short list would make every figure below meaningless."""
    assert len(sentences["human"]) >= 30 and len(sentences["ai"]) >= 30


@pytest.mark.slow
def test_ai_sentences_are_at_the_ceiling(scored):
    """The premise. If AI sentences did not saturate, the human ones saturating would not matter."""
    at_ceiling = sum(x >= 0.99 for x in scored["ai"])
    assert at_ceiling >= 0.8 * len(scored["ai"]), f"{at_ceiling}/{len(scored['ai'])}"


@pytest.mark.slow
def test_human_sentences_also_reach_the_ceiling(scored):
    """The finding. A ranking cannot separate what the detector scores identically.

    This is the sentence-level form of a defect this repository has on record at document level:
    a saturating detector disables selection, and the giveaway is a score that cannot move.
    """
    at_ceiling = sum(x >= 0.99 for x in scored["human"])
    assert at_ceiling >= 0.3 * len(scored["human"]), (
        f"only {at_ceiling}/{len(scored['human'])} human sentences are at the ceiling — if that "
        "improved, the docstring's re-measurement is stale and should be redone"
    )


@pytest.mark.slow
def test_most_human_sentences_flag_at_the_shipped_cut(scored):
    """What a caller actually sees: the flagged list is mostly human on mixed input."""
    flagged = sum(x >= 0.30 for x in scored["human"])
    assert flagged >= 0.7 * len(scored["human"]), f"{flagged}/{len(scored['human'])}"


@pytest.mark.slow
def test_separation_is_well_below_the_documented_floor(scored):
    """0.886 was the documented floor for model-backed detectors; the ensemble max is near 0.81."""
    def auroc(pos, neg):
        return sum((p > n) + 0.5 * (p == n) for p in pos for n in neg) / (len(pos) * len(neg))

    assert auroc(scored["ai"], scored["human"]) < 0.886, (
        "sentence-level separation now clears the documented floor — good news, and the docstring "
        "re-measurement should be updated rather than this assertion deleted"
    )
