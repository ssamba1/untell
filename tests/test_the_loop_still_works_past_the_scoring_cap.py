"""The objective is truncated at 50,000 characters. The loop must still work past it.

`score_text` sees only the first 50,000 characters, so best-of-N selection is blind to everything
beyond — a candidate is chosen on a prefix while the rewriter edits the whole document. The obvious
worry is that crossing the cap breaks the loop: the score stops responding to most of the text, so
nothing looks like an improvement and nothing gets adopted.

It does not. MEASURED across four sizes of the same generated corpus, one iteration, best_of=3:

    paras   chars    cap      changed  adopted  tells cleared
       20    6,638   under      yes       1        46%
       60   19,958   under      yes       1        37%
      140   46,678   under      yes       1        34%
      200   66,778   OVER       yes       1        33%

No discontinuity at the boundary. The decline across the range is the composition effect recorded
in `test_rewriting_reaches_the_end_of_a_long_document.py` — repetition's share of the tells grows
with length and repetition is the category the rewriter barely moves — not a truncation effect.

WHAT IS NOT SHOWN HERE. The blind-tail risk is real in principle: nothing in the selection can
reject a candidate that improves the prefix and damages the unscored tail. I tried to construct
that harm — an AI prefix past the cap with clean human text entirely beyond it — and could not
observe it, because on that document the loop adopted nothing at all and the tail was never
touched. So this file pins the property that IS established, and says plainly that the other one
is unproven rather than implying it was ruled out.
"""

from __future__ import annotations

import pytest

from untell.scripts.run import untell_text
from untell.scripts.score import MAX_INPUT_CHARS

# The cap is 50,000 characters, so the fixture cannot be smaller than that and still be about the
# cap — one loop run over 53k takes ~6 minutes. Marked like the other expensive files here so
# `pytest -m "not slow"` stays fast, rather than trimmed into a test that no longer crosses the
# boundary it exists for.
pytestmark = pytest.mark.slow

_SUBJECTS = [
    "climate adaptation", "protein folding", "urban transit", "credit scoring", "soil carbon",
    "vaccine logistics", "grid storage", "coral restoration", "supply chains", "wildfire modelling",
]
_OPENERS = ["Moreover,", "Furthermore,", "Additionally,", "Notably,", "In conclusion,"]
# Varied verb and noun phrases, NOT one fixed phrasing. Written first with a single hardcoded
# "leverages a robust framework" in every paragraph, and the loop then adopted nothing at all —
# repetition dominates such a document and the rewriter cannot move the score. That is a property
# of the fixture, not of the cap, and it would have been recorded here as the opposite finding.
# This builder is the one that produced the measured table above.
_VERBS = ["leverages", "underscores", "delves into", "highlights", "showcases"]
_NOUNS = [
    "a robust framework", "the pivotal integration", "a multifaceted tapestry",
    "the comprehensive landscape", "a transformative paradigm",
]


def _build(paragraphs: int) -> str:
    out = []
    for i in range(paragraphs):
        subject = _SUBJECTS[i % len(_SUBJECTS)]
        out.append(
            f"{_OPENERS[i % 5]} the study of {subject} in region {i} {_VERBS[i % 5]} "
            f"{_NOUNS[i % 5]} for every stakeholder. It is important to note that {subject} "
            f"demonstrates remarkable capabilities in trial {i}. {_OPENERS[(i + 2) % 5]} "
            f"researchers leveraged these seamless tools to accelerate discovery across the "
            f"{subject} domain and beyond."
        )
    return "\n\n".join(out)


@pytest.fixture(autouse=True)
def stdlib_lite(monkeypatch):
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")


@pytest.fixture(scope="module")
def oversized() -> str:
    """The smallest generated document that clears the cap, so the test costs as little as the
    property allows — every extra paragraph is real rewriting work on every run."""
    paragraphs = 160
    while len(_build(paragraphs)) <= MAX_INPUT_CHARS:
        paragraphs += 20
    return _build(paragraphs)


@pytest.fixture(scope="module")
def run(oversized: str) -> dict:
    """ONE loop run, shared by every case.

    Written first as three tests each calling `untell_text` on a 50k+ document, which did not
    finish inside the timeout. Every run here rewrites the whole document; the cost is in the runs,
    so three assertions about one result cost a third of three results.
    """
    import os

    os.environ["UNTELL_LITE_NO_TORCH"] = "1"
    return untell_text(
        oversized, tier="lite", rewriter="composite", max_iters=1, best_of=3,
        threshold=0.001, seed=3,
    )


def test_the_fixture_really_is_over_the_cap(oversized: str) -> None:
    """The premise. Under the cap this file is asserting nothing about truncation."""
    assert len(oversized) > MAX_INPUT_CHARS


def test_the_loop_still_rewrites_past_the_cap(run: dict) -> None:
    result = run
    assert result["changed"], (
        "the loop adopted nothing on a document past the scoring cap — truncating the objective "
        "has stopped it recognising an improvement"
    )
    assert result["adopted"] >= 1


def test_it_still_clears_tells_past_the_cap(run: dict) -> None:
    result = run
    before, after = result["tells_before"], result["tells_after"]
    assert before > 0, "fixture carries no tells; nothing to clear"
    cleared = (before - after) / before
    # The measured range across sizes is 33-46%; 15% is a floor that catches "stopped working"
    # without pinning a number that moves with the corpus.
    assert cleared > 0.15, (
        f"only {cleared:.0%} of tells cleared past the cap ({before} -> {after}); the measured "
        f"range across four sizes was 33-46%"
    )


def test_the_output_still_covers_the_whole_document(run: dict, oversized: str) -> None:
    """Truncation is of the OBJECTIVE, not the text. A loop that returned only the scored prefix
    would silently delete everything past it.

    Asserted on CONTENT, not on length. Written first as `len(final) > MAX_INPUT_CHARS`, which
    failed at 42,710 characters from a 53,378-character input — and that is not a dropped tail, it
    is a legitimate 0.800 ratio from rewriting, which removes openers and merges clauses. Length
    cannot tell shortening from deletion; a marker that only exists beyond the cap can.
    """
    result = run
    beyond = []
    index = 0
    while True:
        marker = f"region {index}"
        position = oversized.find(marker)
        if position < 0:
            break
        if position > MAX_INPUT_CHARS:
            beyond.append(index)
        index += 1

    assert beyond, "no paragraph starts beyond the cap; this fixture cannot show a dropped tail"
    missing = [i for i in beyond if f"region {i}" not in result["final"]]
    assert not missing, (
        f"{len(missing)} of {len(beyond)} paragraphs that begin beyond the scoring cap are absent "
        f"from the output ({missing[:5]}) — the unscored tail was dropped, not merely unscored"
    )
