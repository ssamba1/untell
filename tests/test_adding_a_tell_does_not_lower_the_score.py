"""The assumption the whole product rests on, measured for the first time.

untell removes catalogued tells in order to lower a detector score. Nothing had checked the premise
in the other direction: that ADDING those tells raises it. If a phrase the catalogue calls an AI tell
leaves the detector unmoved, removing it cannot help; if it lowers the detector, removing it actively
hurts, and the loop would be optimising against itself.

MEASURED, 20 HC3 human halves, 8 catalogued openers injected at the front of successive sentences,
full tier, per document rather than on the mean:

    detector                  up   down   flat
    max (ensemble)            20      0      0
    perplexity_burstiness     20      0      0
    mage                      18      1      1
    roberta_openai            11      2      7
    fast_detectgpt            11      9      0
    hc3_roberta               10      1      9

The ensemble rises on every document. Two members are close to directionless on this manipulation —
`fast_detectgpt` at 11/9 is a coin flip, and `hc3_roberta` does not move at all on 9 of 20 — which is
worth knowing but is not the same as being wrong.

**The mean said something else, and it was wrong.** Averaged over 10 documents, `roberta_openai`
reads 0.100 -> 0.013 and `fast_detectgpt` 0.091 -> 0.074, both monotonically falling across 0, 2 and
8 injections. That looks exactly like two detectors pointing backwards. The per-document record says
11 up / 2 down / 7 flat: a couple of large drops dragged an average that most documents moved the
other way. The aggregate is not a summary of the record here, it contradicts it.

On the lite tier the corpus means read 0.330 at zero injections, 0.412 at two and 0.413 at eight,
which looks like saturation after the first couple of tells. Do not read it that way without
checking the harness: on short texts the identical-looking tail is this injector running out of
eligible sentences, not the detector running out of response. See
`test_the_low_dose_response_is_not_monotone`.
"""

from __future__ import annotations

import logging

import pytest

from untell.scripts.score import score_text
from untell.text_split import split_sentences

TELLS = [
    "Moreover, it is important to note that ",
    "Furthermore, this underscores the fact that ",
    "In today's fast-paced world, ",
    "It is worth noting that ",
    "Ultimately, this highlights the reality that ",
    "Additionally, it should be emphasised that ",
]
CLEAN = [
    "Salt lowers the freezing point of water, which is why councils spread it on roads in winter. "
    "It works down to about minus nine degrees, below which other chemicals are needed instead. "
    "The grit does a second job once the ice has gone soft, which matters more on a hill.",
    "The bridge was closed for four months while the deck was replaced. Traffic was diverted "
    "through the village, and the council paid for a temporary crossing upstream. Residents "
    "complained about the noise, and the contractor agreed to shorter working hours.",
    "She kept every receipt in a shoebox under the desk. When the audit came, the box was the only "
    "record that survived the flood, and the inspector went through it line by line. It took two "
    "days, and everything balanced except a single postage entry.",
]


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


def inject(text: str, n: int) -> str:
    sentences = split_sentences(text)
    out, used = [], 0
    for sentence in sentences:
        if used < n and len(sentence.split()) > 6:
            out.append(TELLS[used % len(TELLS)] + sentence[0].lower() + sentence[1:])
            used += 1
        else:
            out.append(sentence)
    return " ".join(out)


@pytest.mark.parametrize("text", CLEAN, ids=["salt", "bridge", "receipts"])
def test_injecting_tells_does_not_lower_the_score(text: str) -> None:
    """The premise, stated as the weakest form that must hold: adding eight catalogued AI tells
    must not make the detector *less* suspicious. Measured 20 of 20 on corpus text; asserted here
    with a small tolerance so detector jitter is not a failure."""
    before = score_text(text, tier="lite")["max"]
    after = score_text(inject(text, 8), tier="lite")["max"]
    assert after >= before - 0.01, (before, after)


@pytest.mark.parametrize("text", CLEAN, ids=["salt", "bridge", "receipts"])
def test_a_full_dose_raises_the_score(text: str) -> None:
    """Guards the guard from the other side. `>=` above is satisfied by a detector that ignores
    tells entirely, which would be the more interesting defect — it would mean the loop's entry
    condition is disconnected from the catalogue it rewrites against.

    Asserted at a FULL dose, because a small one does not license this claim — see below."""
    before = score_text(text, tier="lite")["max"]
    after = score_text(inject(text, 8), tier="lite")["max"]
    assert after > before + 0.05, (before, after)


@pytest.mark.parametrize("text", CLEAN, ids=["salt", "bridge", "receipts"])
def test_the_low_dose_response_is_not_monotone(text: str) -> None:
    """Recorded because the first version of the test above asserted "two tells raise the score" and
    it is FALSE. The dose-response measured at 0, 1, 2, 3, 4, 6 and 8 injections:

        salt      0.678  0.593  0.708  0.748  0.748  0.748  0.748
        bridge    0.631  0.622  0.619  0.727  0.727  0.727  0.727
        receipts  0.377  0.558  0.464  0.541  0.541  0.541  0.541

    One tell LOWERS "salt" by 0.085; two lower "bridge". Every document ends higher than it started
    and none of them gets there monotonically, so a claim about a small dose is not supported by a
    measurement of a large one.

    The flat tail from 3 onward is **not** the detector saturating — it is this injector running out
    of sentences. Each of these texts has three sentences long enough to take an opener, so n=3 and
    n=8 are the same document. That distinction is the difference between a fact about the detector
    and a fact about the harness, and only one of them belongs in a docstring.
    """
    scores = [score_text(inject(text, n), tier="lite")["max"] for n in (0, 1, 2, 3)]
    assert scores[-1] > scores[0], scores
    assert min(scores) < scores[0] or scores[1] > scores[2], scores


@pytest.mark.parametrize("text", CLEAN, ids=["salt", "bridge", "receipts"])
def test_the_tell_catalogue_counts_what_was_injected(text: str) -> None:
    """The catalogue and the detector are different instruments, and this file is about their
    relationship — so the catalogue's own response is worth pinning separately. It is linear where
    the lite detector saturates: 0.47 per 100 words at zero injections, 5.82 at eight."""
    from untell.scripts.tells import score_tells

    # `tells_per_100w`, not `per_100w`. The wrong key returns None and a fallback rendered it as a
    # flat 0.00 at every injection level — a dead column that looked like a dead metric.
    before = score_tells(text)["tells_per_100w"]
    after = score_tells(inject(text, 4))["tells_per_100w"]
    assert after > before + 1.0, (before, after)


@pytest.mark.slow
def test_the_ensemble_agrees_on_the_corpus() -> None:
    """The measurement above on real text, at the sample size that produced the table. Slow because
    it loads the full ensemble; skipped when the corpora are absent."""
    pytest.importorskip("datasets")
    from eval.datasets import load_pairs

    try:
        pairs = load_pairs("hc3", n=24, min_words=60)
    except Exception as exc:  # noqa: BLE001 - corpus availability is environmental
        pytest.skip(f"hc3 unavailable: {exc}")
    texts = [h for h, _ in pairs][:10]
    lowered = [
        t for t in texts
        if score_text(inject(t, 8), tier="lite")["max"] < score_text(t, tier="lite")["max"] - 0.01
    ]
    assert not lowered, f"{len(lowered)} of {len(texts)} documents scored LOWER with tells added"
