"""Tell removal must not fall off with position.

The detectors once read only the first ~380 words, and `windowed_max` fixed the SCORING. Rewriting
is a separate question with a worse failure mode: a long document whose opening is cleaned and whose
tail is untouched gets a good headline number, while the part a reader reaches last still carries
every tell. Nothing measured it.

MEASURED on 20 distinct tell-bearing paragraphs, 892 words, catalogued tells per fifth:

    before   100  100   99  100  101
    after     56   59   54   51   53
    survival 0.56 0.59 0.55 0.51 0.52

No gradient — the last fifth does marginally better than the first — and 0 of 20 paragraphs were
left untouched.

The first version of this used 20 IDENTICAL paragraphs, so that every position would start equal.
It does, at 214 tells per fifth scored in isolation. But the catalogue counts REPETITION, so most of
those 214 exist only because the paragraphs are copies, and rewriting turns 20 copies into 20
different paragraphs — which drops the repetition tells whether or not one catalogued phrase was
removed. Its 1302 -> 772 was not a tell-removal rate at all. Distinct paragraphs give up the equal
starting point and buy a number that means something; the ratio per fifth is what the positional
question needs anyway.
"""

from __future__ import annotations

import pytest

from untell.scripts.run import untell_text
from untell.scripts.tells import score_tells

SUBJECTS = [
    "climate adaptation", "protein folding", "urban transit", "credit scoring", "soil carbon",
    "vaccine logistics", "grid storage", "coral restoration", "supply chains", "wildfire modelling",
    "language teaching", "water reuse", "orbital debris", "crop rotation", "noise abatement",
    "port automation", "flood mapping", "dialect survey", "seed banking", "tunnel ventilation",
]
OPENERS = ["Moreover,", "Furthermore,", "Additionally,", "Notably,", "In conclusion,"]
VERBS = ["leverages", "underscores", "delves into", "highlights", "showcases"]
NOUNS = ["a robust framework", "the pivotal integration", "a multifaceted tapestry",
         "the comprehensive landscape", "a transformative paradigm"]

PARAS = [
    f"{OPENERS[i % 5]} the study of {subject} {VERBS[i % 5]} {NOUNS[i % 5]} for every stakeholder. "
    f"It is important to note that {subject} demonstrates remarkable capabilities in practice. "
    f"{OPENERS[(i + 2) % 5]} researchers have leveraged these seamless tools to accelerate "
    f"discovery across the entire {subject} domain and beyond."
    for i, subject in enumerate(SUBJECTS)
]
DOC = "\n\n".join(PARAS)


def _tells_per_fifth(text: str) -> list[int]:
    paras = [p for p in text.split("\n\n") if p.strip()]
    step = max(1, len(paras) // 5)
    return [score_tells("\n\n".join(paras[i:i + step]))["tells"]
            for i in range(0, len(paras), step)][:5]


@pytest.fixture(scope="module")
def rewritten(request) -> dict:
    """One run, shared. The threshold is forced low so the loop keeps working rather than stopping
    at `passed` on the first iteration — this asks where rewriting lands, not whether it stops."""
    mp = pytest.MonkeyPatch()
    mp.setenv("UNTELL_LITE_NO_TORCH", "1")
    request.addfinalizer(mp.undo)
    return untell_text(DOC, tier="lite", max_iters=3, rewriter="composite", best_of=3, seed=21,
                       threshold=0.001)


def test_the_document_starts_evenly_loaded() -> None:
    """The premise. A positional claim needs a flat starting profile to be about position."""
    before = _tells_per_fifth(DOC)
    assert min(before) > 0
    assert max(before) - min(before) <= 0.1 * max(before), f"uneven source: {before}"


def test_tells_fall_in_every_fifth(rewritten: dict) -> None:
    before, after = _tells_per_fifth(DOC), _tells_per_fifth(rewritten["final"])
    for i, (b, a) in enumerate(zip(before, after)):
        assert a < b, f"fifth {i} did not improve: {b} -> {a} (all fifths: {before} -> {after})"


def test_the_tail_is_not_treated_worse_than_the_head(rewritten: dict) -> None:
    """The failure this file exists for: a cleaned opening over an untouched tail."""
    before, after = _tells_per_fifth(DOC), _tells_per_fifth(rewritten["final"])
    survival = [a / b for a, b in zip(after, before)]
    head, tail = survival[0], survival[-1]
    assert tail <= head + 0.25, (
        f"the last fifth keeps {tail:.2f} of its tells against the first fifth's {head:.2f}; "
        f"rewriting is thinning out toward the end of the document: {survival}"
    )


def test_no_paragraph_is_skipped(rewritten: dict) -> None:
    out = [p for p in rewritten["final"].split("\n\n") if p.strip()]
    assert len(out) == len(PARAS), f"paragraph count changed: {len(PARAS)} -> {len(out)}"
    untouched = [i for i, (a, b) in enumerate(zip(out, PARAS)) if a.strip() == b.strip()]
    assert not untouched, f"paragraphs returned verbatim: {untouched}"


# The overall clearance rate falls steeply with length, and the reason is composition, not reach.
# MEASURED on prefixes of this document, `max_iters=3`:
#
#     paras  words  tells cleared   repetition share of source tells
#         1     44    6->0   100%    0%
#         2     88   35->11   69%   63%
#         4    178  100->52   48%   72%
#         8    357 258->143   45%   78%
#        20    892 769->422   45%   82%
#
# Every non-repetition category clears completely at every length; repetition clears about a third.
# So the aggregate slides toward the repetition rate as repetition takes over the source, and the
# model reproduces the totals — at 20 paragraphs, 140 non-repetition cleared fully plus 629 * 0.34
# predicts 354 against 347 observed. The meaning gate is not involved: 0 refusals out of 9 draws at
# every length measured.
#
# That repetition is the largest untreated tell is already recorded (see composite.py). What is
# recorded here is the document-level consequence: a headline clearance rate is largely a statement
# about how repetitive the input is, so quoting one without its composition says little.
#
# This fixture is TEMPLATED — 20 paragraphs from one skeleton — which inflates repetition by
# construction and makes it a floor for the effect, not an estimate of it on real prose.
#
# The iteration budget is not what limits it either. On this document the loop converges in the
# FIRST iteration and the rest is spent for nothing:
#
#     max_iters   1     3     5     8
#     tells     422   422   422   422        (byte-identical output at every setting, seed 21)
#     rewrites    3     9    15    24
#
# Across three seeds at max_iters 1 vs 5, two give byte-identical output for 5x the rewrites and
# the third gains 2 tells of 769. The stall check that would stop this only applies to rewriters
# declaring `deterministic`, and composite is stochastic, so a non-improving round is not proof
# that the next one fails. A patience rule (stop after K rounds adopting nothing) would clearly pay
# here, but one templated document at three seeds is not enough to set K or to know what it costs
# on short, low-repetition input where iteration does still earn its keep — so it is recorded, not
# shipped.
REPETITION_CATEGORIES = ("repeated_phrasing", "repeated_sentence_openers")


def test_every_non_repetition_category_is_cleared_completely(rewritten: dict) -> None:
    """The reach guard. If the rewriter ever stops reaching the vocabulary, cliche, transition or
    opener tells in a long document, that is a regression the aggregate rate would hide — it would
    move a few points and stay in the same band as the repetition residue."""
    before = score_tells(DOC)["by_category"]
    after = score_tells(rewritten["final"])["by_category"]

    checked = {c: n for c, n in before.items() if c not in REPETITION_CATEGORIES}
    assert len(checked) >= 3, f"too few non-repetition categories to be a real check: {checked}"

    survivors = {c: (checked[c], after.get(c, 0)) for c in checked if after.get(c, 0)}
    assert not survivors, f"non-repetition tells survived a long-document run: {survivors}"


def test_repetition_is_the_residue_and_is_still_reduced(rewritten: dict) -> None:
    """Names the known limit without excusing it. Repetition must still fall — a rewriter that
    stopped touching it entirely would otherwise pass the test above and look healthy."""
    before = score_tells(DOC)["by_category"]
    after = score_tells(rewritten["final"])["by_category"]

    b = sum(before.get(c, 0) for c in REPETITION_CATEGORIES)
    a = sum(after.get(c, 0) for c in REPETITION_CATEGORIES)
    assert b > 0, "fixture carries no repetition tells; this asserts nothing"
    assert a < b, f"repetition did not fall at all: {b} -> {a}"
    assert a > 0, (
        f"repetition cleared completely ({b} -> {a}) — that would be a real improvement, and the "
        f"composition finding recorded above needs re-measuring rather than this test relaxing"
    )
