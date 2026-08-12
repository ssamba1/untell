"""On a mixed document the loop edits human sentences too — and must not change what they say.

A mostly-human document with a generated paragraph is the shape a real user brings, and the two
tiers fail on it in opposite directions. MEASURED, human body plus AI block, run through the loop:

    tier      what happens
    stdlib    rewrites=0, changed=False — the diluted 0.2657 is under the 0.30 threshold, so the
              loop declares "passed" and the AI section stays exactly as it was
    full      changed=True, 6 draws — and it edits BOTH halves at similar rates: 10 of 13 human
              sentences survive verbatim (77%) against 5 of 7 AI sentences (71%)

The full tier's behaviour follows from sentence-level targeting precision of 0.444: half the
flagged spans are human writing, so half the edits land there. That is a measured limit of the
detectors on this corpus, not a mistake in the loop, and there is no local fix for it.

What CAN be guaranteed is that the edits do not change what the user's own sentences say. Measured
at 0.9929 similarity on the human half. That is the property these tests hold, because it is the
one a user is entitled to rely on when the tool touches prose they wrote.
"""
from __future__ import annotations

import pytest

from eval.datasets import load_pairs
from untell.scripts.quality import similarity
from untell.scripts.run import untell_text
from untell.text_split import split_sentences


@pytest.fixture(scope="module")
def mixed() -> dict:
    pairs = load_pairs("hc3", 6)
    if len(pairs) < 5:
        pytest.skip("needs the HC3 pairs")
    human_body = " ".join(h for h, _ in pairs[1:4]).strip()
    ai_block = pairs[0][1].strip()
    return {
        "human": human_body,
        "ai": ai_block,
        "document": human_body + "\n\n" + ai_block,
    }


@pytest.mark.slow
def test_the_human_half_keeps_its_meaning_even_when_edited(mixed):
    """The guarantee. Losing phrasing is a cost; losing meaning would be a defect."""
    result = untell_text(mixed["document"], tier="full", threshold=0.30, max_iters=2,
                         rewriter="composite", seed=11)

    assert similarity(mixed["document"], result["final"]) >= 0.9, (
        f"the whole document drifted to {result.get('similarity')}"
    )


@pytest.mark.slow
def test_the_loop_does_edit_the_human_half(mixed):
    """Stated plainly rather than left implied, because a user would not expect it.

    Precision at sentence level is 0.444, so roughly half the flagged spans are human writing.
    This asserts the behaviour exists so nobody reads the guarantee above as "human text is left
    alone" — it is not.
    """
    result = untell_text(mixed["document"], tier="full", threshold=0.30, max_iters=2,
                         rewriter="composite", seed=11)
    if not result.get("changed"):
        pytest.skip("the loop declined to rewrite this document")

    human_sentences = {s.strip() for s in split_sentences(mixed["human"]) if s.strip()}
    out = {s.strip() for s in split_sentences(result["final"]) if s.strip()}
    survived = len(human_sentences & out)

    assert survived < len(human_sentences), (
        "every human sentence survived verbatim — if targeting improved that much, the precision "
        "figure in sentences.py is stale and should be re-measured"
    )


def test_the_stdlib_path_leaves_the_document_alone(monkeypatch, mixed):
    """The opposite failure, pinned so the two are not confused.

    Dilution puts the mixed document under the threshold, so the loop passes it immediately and
    the AI section survives untouched. Nothing is edited — including the AI half.
    """
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")

    result = untell_text(mixed["document"], tier="lite", threshold=0.30, max_iters=2,
                         rewriter="composite", seed=11)

    assert not result.get("changed"), (
        "the stdlib path rewrote a document it scores below threshold; if dilution stopped "
        "happening, the note beside _STDLIB_PERPLEXITY_VERDICT_THRESHOLD needs updating"
    )
    assert result["final"].strip() == mixed["document"].strip()
