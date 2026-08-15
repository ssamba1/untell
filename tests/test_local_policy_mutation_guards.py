"""Killing tests for local_policy.py mutation survivors (2026-08-14 sweep).

  line 294  logic: == -> !=        identical-candidate rejection.
  line 300  logic: and -> or       length-band guard.

Killed here. 339 (8-word fragment threshold) is only reachable through the
model-gated rewrite() path — annotated. The other survivors (220/233/245/262/
297/301/305/392/413) are model-load or availability constants.
"""

from __future__ import annotations

from untell.rewriter.local_policy import LocalPolicyRewriter


class TestFaithfulness:
    """Survivors 294/300 — the sentence-acceptance gate.

    A candidate identical to the source is rejected (no rewrite happened). A
    candidate whose length ratio falls outside the band is rejected. Both are
    checked BEFORE any entailment call."""

    def test_identical_candidate_rejected(self) -> None:
        rw = LocalPolicyRewriter()
        assert rw._sentence_is_faithful("The cat sat on the mat.", "The cat sat on the mat.") is False

    def test_out_of_band_length_rejected(self) -> None:
        rw = LocalPolicyRewriter()
        # 10-word source; candidate ratio 5.0 (50 words) — far outside (0.7, 1.4)
        source = "one two three four five six seven eight nine ten"
        candidate = " ".join(f"w{i}" for i in range(50))
        assert rw._sentence_is_faithful(source, candidate) is False

    def test_in_band_length_not_rejected_by_length(self) -> None:
        rw = LocalPolicyRewriter()
        # same length ratio 1.0 — the length band passes; the entailment gate decides
        source = "The cat sat quietly on the warm mat."
        candidate = "The feline rested upon the heated rug."
        # monkeypatched entailment.available -> False: mechanical band only, accepts
        from untell.scripts import entailment

        old = entailment.available
        entailment.available = lambda: False
        try:
            assert rw._sentence_is_faithful(source, candidate) is True
        finally:
            entailment.available = old
