"""The meaning gate judges text that still carries `⟦HZ…⟧` sentinels, and that is fine — measured.

The loop locks preserved spans before rewriting, so `meaning_preserved(masked, candidate, …)`
compares strings where every citation, URL and quantity has become an opaque token. An embedding
model reading those is not reading the document. The targeting path in the same function carries a
full masked-vs-restored analysis for exactly this reason; the gate's comment used to say nothing.

A constructed citation-dense pair suggested it mattered — three locked spans across two sentences
moved similarity **0.8974 -> 0.9304**, inflating it, which is the unsafe direction.

Real text is not that dense. MEASURED over 38 genuine rewrites of corpus texts that DO lock a span
(38 of 50 do, so this is the common case, not an edge):

    similarity masked - restored   mean -0.0014   max +0.0091   min -0.0218
    verdict disagreements          1 of 38, running the SAFE way — masked rejected a candidate
                                   the restored comparison would have admitted

**No defect.** The synthetic probe generalised from a density real documents do not have. Masking is
also principled rather than merely harmless: the sentinel-integrity check immediately above the gate
has already proven every locked span appears identically on both sides, so comparing them again adds
nothing, and what remains is the prose the rewriter actually changed.

What this file pins is the DIRECTION. If masking ever starts admitting what the restored comparison
rejects, that is the direction that ships a damaged document, and the trade above stops holding.
"""

from __future__ import annotations

import logging

import pytest

from untell.scripts.entailment import meaning_preserved
from untell.scripts.preserve import lock, restore
from untell.scripts.quality import similarity

SOURCE = (
    "The framework improves efficiency by 47% across the corpus, as reported in Smith (2020) "
    "and confirmed at https://example.org/paper for every dataset that was tested."
)


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


def test_locking_actually_happens_here() -> None:
    """Premise. With nothing locked the two comparisons are the same string and every assertion
    below passes without touching the question."""
    masked, mapping = lock(SOURCE)
    assert mapping and "⟦HZ" in masked


def test_a_faithful_rewrite_passes_on_both_views() -> None:
    masked, mapping = lock(SOURCE)
    candidate = masked.replace("framework", "setup").replace("every", "each")
    assert meaning_preserved(masked, candidate, similarity(masked, candidate), 0.76)
    real_src, real_cand = restore(masked, mapping), restore(candidate, mapping)
    assert meaning_preserved(real_src, real_cand, similarity(real_src, real_cand), 0.76)


def test_masking_never_admits_what_the_real_text_would_reject() -> None:
    """The direction that matters. A gate loosened by masking would ship a damaged document; one
    tightened by it merely costs a candidate, and the loop draws another."""
    masked, mapping = lock(SOURCE)
    # Meaning inverted, with every locked span reproduced exactly — so the sentinel-integrity check
    # would pass this and the gate is the only thing standing in its way.
    candidate = masked.replace("improves", "fails to improve")
    real_src, real_cand = restore(masked, mapping), restore(candidate, mapping)
    masked_verdict = meaning_preserved(masked, candidate, similarity(masked, candidate), 0.76)
    real_verdict = meaning_preserved(real_src, real_cand, similarity(real_src, real_cand), 0.76)
    assert not (masked_verdict and not real_verdict), (masked_verdict, real_verdict)


def test_the_sentinels_are_identical_on_both_sides_by_the_time_the_gate_runs() -> None:
    """Why masking costs nothing in principle: the integrity check above the gate has already
    rejected any candidate whose sentinels differ, so the masked spans carry no information the
    comparison could use."""
    from collections import Counter

    from untell.scripts.preserve import SENTINEL_RE

    masked, _ = lock(SOURCE)
    candidate = masked.replace("framework", "setup")
    assert Counter(SENTINEL_RE.findall(candidate)) == Counter(SENTINEL_RE.findall(masked))
