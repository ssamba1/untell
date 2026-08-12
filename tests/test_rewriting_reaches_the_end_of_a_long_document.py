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
