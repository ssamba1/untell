"""`unrankable` catches the documents where ranking is impossible, not the ones where it is wrong.

`score_sentences` sets `unrankable` when a document's own per-sentence scores span less than 0.05.
That is the right shape for the problem it solves — a per-document test rather than a blanket
warning — and MEASURED at full tier it lands where it should:

    document                    sentences   spread    unrankable
    ai doc0                          7      0.0047      True
    ai doc1                          8      0.0000      True
    ai doc2                          7      0.0066      True
    ai doc3                          7      0.0001      True
    ai doc4                          9      0.0004      True
    ai doc5                          8      0.0008      True
    human doc1                       4      0.8877      False
    human doc3                       6      0.8732      False
    human doc4                       6      0.8410      False
    mixed: human body + ai block    20      0.8877      False

Every AI document is caught: each sentence sits at the detector's ceiling, so the ordering carries
no information at all. Wide-spread human documents are left alone.

WHERE IT DOES NOT REACH, and this is a boundary worth writing down rather than discovering later:
spread is not correctness. The mixed document has a spread of 0.8877 and is correctly called
rankable — and targeting it still gave precision 0.444, because two HUMAN sentences scored 1.0000
alongside the AI ones. A ranking can have plenty of range and still put the wrong sentences on top.

So `unrankable` answers "can these scores be ordered at all", which is exactly what it claims, and
not "is the order right". Both tests below exist so the first is not mistaken for the second.
"""
from __future__ import annotations

import pytest

from eval.datasets import load_pairs
from untell.scripts.sentences import score_sentences


@pytest.fixture(scope="module")
def corpus() -> list:
    pairs = load_pairs("hc3", 8)
    if len(pairs) < 6:
        pytest.skip("needs the HC3 pairs")
    return pairs


def _spread(result: dict) -> float:
    scores = [row["ai"] for row in result["sentences"]]
    return max(scores) - min(scores) if scores else 0.0


@pytest.mark.slow
def test_a_saturated_document_is_marked_unrankable(corpus):
    """Every sentence at the ceiling means the ordering carries no information."""
    marked = 0
    for _human, ai in corpus[:6]:
        result = score_sentences(ai, tier="full")
        if _spread(result) < 0.05:
            assert result.get("unrankable"), (
                f"spread {_spread(result):.4f} but unrankable is {result.get('unrankable')!r}"
            )
            marked += 1
    assert marked >= 4, f"only {marked} of 6 AI documents saturated; the premise may be stale"


@pytest.mark.slow
def test_a_document_with_real_spread_is_not_marked(corpus):
    """The other side. Marking everything would make the field useless."""
    unmarked = 0
    for human, _ai in corpus[:6]:
        result = score_sentences(human, tier="full")
        if _spread(result) >= 0.05:
            assert not result.get("unrankable"), (
                f"spread {_spread(result):.4f} was still called unrankable"
            )
            unmarked += 1
    assert unmarked >= 2, f"only {unmarked} human documents had usable spread"


@pytest.mark.slow
def test_wide_spread_does_not_mean_the_order_is_right(corpus):
    """The boundary. `unrankable` is about range, and range is not accuracy.

    A document built from a human body plus an AI block has plenty of spread and is correctly
    called rankable — and its flagged list was still 5/9 human sentences when measured, because
    human sentences from this corpus also reach 1.0000. Nothing here is broken; the point is that
    a False `unrankable` is not a promise the ranking is correct, and a reader could easily take
    it as one.
    """
    human_body = " ".join(h for h, _ in corpus[1:4])
    mixed = human_body + "\n\n" + corpus[0][1]

    result = score_sentences(mixed, tier="full")

    assert _spread(result) >= 0.05
    assert not result.get("unrankable"), "the mixed document has range; it should not be marked"
    assert result["flagged"], "nothing flagged, so there is no ordering to be right or wrong about"
