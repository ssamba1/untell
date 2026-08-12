"""A generated paragraph inside a human document is invisible to the stdlib path.

The shape a real user brings is a mostly-human document with a generated section in it. MEASURED,
a 207-word AI block inside 567 words of human writing, scored whole:

    position of the AI block      stdlib      full tier
    alone, no filler              0.6239        1.0000
    at the start                  0.2657        1.0000
    in the middle                 0.2657        1.0000
    at the end                    0.2657        0.9999
    (human filler alone)          0.2586        0.0936

On the stdlib path the section is gone: 0.2657 sits below both the 0.30 loop threshold and the
0.45 verdict cut, and barely moves off the human filler's own 0.2586. Position makes no difference
because both of that path's terms are document-wide aggregates. The full tier flags it wherever it
sits — that is what `windowed_max` exists for.

NOT a defect to fix by windowing the stdlib path. That was measured and rejected: the note in
`perplexity_burstiness.score` records windowing taking FPR from 30% to 90% on three-paragraph
documents while buying no true positives, because burstiness across a document is precisely the
quantity a window destroys. The honest answer is the tier.

These tests pin the contrast rather than the numbers — an exact 0.2657 would be brittle across
detector changes, while "the full tier sees it and the stdlib path does not" is the property a
user's decision rests on.
"""
from __future__ import annotations

import pytest

from eval.datasets import load_pairs
from untell.scripts.score import score_text


@pytest.fixture(scope="module")
def mixed() -> dict:
    pairs = load_pairs("hc3", 6)
    if len(pairs) < 6:
        pytest.skip("needs the HC3 pairs")
    human = [h for h, _ in pairs]
    ai = [a for _, a in pairs]
    filler = " ".join(human[1:5])
    return {
        "ai_block": ai[0].strip(),
        "filler": filler,
        "at_end": filler + "\n\n" + ai[0].strip(),
        "at_start": ai[0].strip() + "\n\n" + filler,
    }


def test_the_ai_block_is_flagged_on_its_own_at_lite(monkeypatch, mixed):
    """The premise. If the block did not score high alone, dilution would prove nothing."""
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
    assert score_text(mixed["ai_block"], tier="lite")["max"] >= 0.45


def test_the_filler_is_human_enough_to_dilute(monkeypatch, mixed):
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
    assert score_text(mixed["filler"], tier="lite")["max"] < 0.45


@pytest.mark.parametrize("position", ["at_start", "at_end"])
def test_the_stdlib_path_loses_the_embedded_section(monkeypatch, mixed, position: str):
    """The limitation, pinned as it behaves so a user's tier choice rests on something checked."""
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")

    alone = score_text(mixed["ai_block"], tier="lite")["max"]
    embedded = score_text(mixed[position], tier="lite")["max"]

    assert embedded < alone - 0.2, (
        f"the AI block scored {alone:.4f} alone and {embedded:.4f} embedded; if dilution stopped "
        "happening the note beside _STDLIB_PERPLEXITY_VERDICT_THRESHOLD needs updating"
    )


@pytest.mark.slow
@pytest.mark.parametrize("position", ["at_start", "at_end"])
def test_the_full_tier_still_finds_it(monkeypatch, mixed, position: str):
    """The reason the answer is 'use the full tier' rather than 'this cannot be detected'."""
    monkeypatch.delenv("UNTELL_LITE_NO_TORCH", raising=False)
    from untell.detectors.perplexity_burstiness import PerplexityBurstinessDetector

    if PerplexityBurstinessDetector().mode() != "gpt2":
        pytest.skip("torch is not importable here, so there is no full tier to check")

    assert score_text(mixed[position], tier="full")["max"] >= 0.9, (
        "the full tier lost an embedded AI section — windowed_max is what should prevent that"
    )
