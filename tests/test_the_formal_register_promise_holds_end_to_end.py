"""`--style academic` promises a formal register. Check it from the OUTSIDE.

The promise is made by knobs — contractions off, the plain-word swap held back, and (recently) a
formal opener pool — and each is enforced at ONE call site. That is exactly how the opener gap
happened: the profile said formal, one transform honoured it, another did not, and nothing checked
across them. A per-knob test cannot catch the next one, because it asks whether the knob was read
rather than whether the output is formal.

So this asks the output. MEASURED over 120 rewrites per style, three formal source documents:

    style          contractions/casual words introduced
    None           120   (isn't 40, can't 40, doesn't 40)
    casual         120   (isn't 40, can't 40, doesn't 40)
    academic         0
    professional     0
    technical        0

The contraction knob is kept. That is a negative result and it is the point: it says the pipeline
respects the profile everywhere it matters for this property, which is what the opener gap
disproved for that one.

The premise matters more than usual here. An earlier version of this measurement used formal source
text containing no contractible forms at all, and reported a clean 0 for EVERY style including the
default — the answer that looks like success. The fixtures now carry "do not", "cannot", "is not",
"it is", and the test asserts they do.
"""

from __future__ import annotations

import random
import re

import pytest

from untell.rewriter.structural import structural_rewrite

PAPERS = [
    "The study examined soil carbon at eleven sites over four years, sampling to ninety centimetres. "
    "Mean stocks were 82.4 t/ha in the deepest layer, against 41.7 t/ha at the surface. "
    "Prior work reported 78.9 t/ha using the same protocol at three of the sites. "
    "The discrepancy is attributable to bulk-density correction. It is not an artefact of "
    "sampling, and we have not observed it at the remaining sites.",
    "This paper introduces a method for estimating boundary layers under sparse observation. "
    "The estimator is consistent under mild regularity conditions and converges at the parametric "
    "rate. Simulation results indicate that the approach outperforms three established baselines. "
    "We do not claim optimality, and the estimator cannot be applied when the design is unbalanced.",
    "The specification defines the wire format, the handshake sequence and the error taxonomy. "
    "Implementations must reject frames whose declared length exceeds the negotiated maximum. "
    "A receiver that encounters an unknown opcode terminates the connection with status 1003. "
    "A peer that does not advertise an extension must not send it, and it is an error to assume "
    "support that was not negotiated.",
]

FORMAL_STYLES = ["academic", "professional", "technical"]
SEEDS = range(40)

CONTRACTION_RE = re.compile(
    r"\b(?:don't|doesn't|didn't|it's|that's|we've|we're|we'll|isn't|aren't|wasn't|weren't|"
    r"can't|won't|couldn't|shouldn't|wouldn't|there's|here's|you're|they're|I'm|let's|"
    r"hasn't|haven't|hadn't|ain't)\b",
    re.IGNORECASE,
)
CASUAL_RE = re.compile(
    r"\b(?:pretty much|pretty|a lot of|a lot|kind of|sort of|really|stuff|"
    r"way too|super|totally|bunch of|loads of|okay)\b",
    re.IGNORECASE,
)
CONTRACTIBLE_RE = re.compile(
    r"\b(?:do not|does not|is not|it is|cannot|was not|have not|must not|that is|we have)\b",
    re.IGNORECASE,
)


def _rewrites(style: str | None) -> list[str]:
    out = []
    for paper in PAPERS:
        for seed in SEEDS:
            random.seed(seed)
            out.append(structural_rewrite(paper, intensity=0.7, style=style))
    return out


def test_the_source_is_formal_and_contractible() -> None:
    """Both halves of the premise. Without contractible forms, "no contractions out" is vacuous;
    with contractions already in, it is unattributable."""
    contractible = sum(len(CONTRACTIBLE_RE.findall(p)) for p in PAPERS)
    assert contractible >= 8, f"only {contractible} contractible forms in the source"
    for paper in PAPERS:
        assert not CONTRACTION_RE.search(paper), "source already contains a contraction"
        assert not CASUAL_RE.search(paper), "source already contains casual vocabulary"


@pytest.mark.parametrize("style", FORMAL_STYLES)
def test_a_formal_style_introduces_no_contraction(style: str) -> None:
    found: dict[str, int] = {}
    for out in _rewrites(style):
        for m in CONTRACTION_RE.findall(out):
            found[m.lower()] = found.get(m.lower(), 0) + 1
    assert not found, f"--style {style} contracted formal source: {found}"


@pytest.mark.parametrize("style", FORMAL_STYLES)
def test_a_formal_style_introduces_no_casual_vocabulary(style: str) -> None:
    found: dict[str, int] = {}
    for out in _rewrites(style):
        for m in CASUAL_RE.findall(out):
            found[m.lower()] = found.get(m.lower(), 0) + 1
    assert not found, f"--style {style} introduced casual vocabulary: {found}"


def test_the_default_style_does_contract() -> None:
    """Guards the guard, and it is the whole test. A pipeline that had simply stopped contracting
    would pass every case above while the knob did nothing — which is indistinguishable from
    working, from the formal side alone."""
    contracted = sum(1 for out in _rewrites(None) if CONTRACTION_RE.search(out))
    assert contracted > 0, (
        "the default style never contracted a single one of these documents, so the formal "
        "results above say nothing about the knob"
    )
