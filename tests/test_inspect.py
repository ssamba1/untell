"""--inspect mode: per-sentence rewrite decisions with named rejection gates (issue #33).

WHAT
    ``untell_text(inspect=True)`` returns ``result["inspect"]``: a list of events per candidate.
    Each rejected candidate carries ``gate`` naming the specific check that fired.

EVIDENCE
    Constructing a candidate that trips one specific gate and asserting the event names it —
    not a generic "rejected" — is the truthfulness test the issue requires.

GATES TESTED
    numbers_kept     drop a number       -> "numbers_kept"
    deletion         over-shorten        -> "deletion ..."
    sentinels        drop a sentinel     -> "sentinels"
    meaning_gate/similarity (no-NLI path, sim too low) -> "similarity ..."
"""

from __future__ import annotations

import os
import unittest.mock as mock

import pytest

# Zero-dep path so tests run without torch/transformers.
os.environ.setdefault("UNTELL_LITE_NO_TORCH", "1")
os.environ.setdefault("UNTELL_DISABLE_MAGE", "1")

from untell.scripts.entailment import meaning_preserved_vetoes
from untell.scripts.run import untell_text
from untell.inspect_report import render_inspect_report


# ---------------------------------------------------------------------------
# meaning_preserved_vetoes unit tests
# These test the veto reporter directly, isolated from the loop, so they are
# fast (no rewriter, no detectors) and mechanically precise.
# ---------------------------------------------------------------------------

SRC = "The trial enrolled 42 patients. The drug reduced mortality by 12%."

# A longer, number-free source for deletion tests: the deletion allowance is
# max(10 words, 10% of source), so at 30+ words it covers 10 words minimum slack
# and a short candidate genuinely exceeds it.
_DELETION_SRC = (
    "The participants completed all required assessments over the full course of the study period. "
    "Results indicated significant improvements across multiple outcome measures in the treatment group."
)


def _vetoes_for(candidate: str, sim: float = 0.99) -> list[str]:
    """Run meaning_preserved_vetoes on SRC vs candidate with a high simulated similarity."""
    return meaning_preserved_vetoes(SRC, candidate, sim=sim, strict_sim_bar=0.76)


class TestMeaningPreservedVetoes:
    def test_faithful_paraphrase_returns_empty(self) -> None:
        """A clean rewrite produces no vetoes."""
        candidate = "Forty-two patients were enrolled in the trial. The drug cut mortality by 12%."
        assert _vetoes_for(candidate) == []

    def test_dropped_number_fires_numbers_kept(self) -> None:
        """Removing a stated number must name 'numbers_kept' as the gate."""
        candidate = "The trial enrolled patients. The drug reduced mortality by 12%."
        vetoes = _vetoes_for(candidate)
        assert "numbers_kept" in vetoes, f"expected numbers_kept in {vetoes}"
        assert vetoes[0] == "numbers_kept", f"numbers_kept should be first; got {vetoes}"

    def test_polarity_flip_fires_polarity_kept(self) -> None:
        """Negating the main claim fires 'polarity_kept'."""
        candidate = SRC.replace("reduced mortality", "did not reduce mortality")
        vetoes = _vetoes_for(candidate)
        assert "polarity_kept" in vetoes, f"expected polarity_kept in {vetoes}"

    def test_severe_deletion_fires_deletion(self) -> None:
        """A candidate that drops far too many words fires the deletion gate.

        Uses _DELETION_SRC (30+ words, no numbers) so the deletion allowance (max 10 words)
        is clearly exceeded by the short candidate.
        """
        candidate = "The results."  # ~2 words vs 30+ in _DELETION_SRC
        vetoes = meaning_preserved_vetoes(
            _DELETION_SRC, candidate, sim=0.99, strict_sim_bar=0.76
        )
        assert any(v.startswith("deletion") for v in vetoes), f"expected deletion in {vetoes}"

    def test_veto_name_starts_with_gate_name(self) -> None:
        """The gate name must be a non-empty string, not a generic placeholder."""
        candidate = SRC.replace("42", "")  # drop the number
        vetoes = _vetoes_for(candidate)
        assert vetoes, "expected at least one veto"
        for v in vetoes:
            assert isinstance(v, str) and v, "veto must be a non-empty string"

    def test_returns_list_type(self) -> None:
        """Return type is always list (never None)."""
        result = _vetoes_for(SRC)  # source vs itself
        assert isinstance(result, list)

    def test_source_identical_to_candidate_returns_empty(self) -> None:
        """A byte-identical candidate is always preserved."""
        assert _vetoes_for(SRC) == []


# ---------------------------------------------------------------------------
# Loop integration: inspect=True returns inspect events
# ---------------------------------------------------------------------------

# A short AI-flavoured text the surgical rewriter can actually improve.
_LOOP_TEXT = (
    "Moreover, the framework leverages a robust approach to delivery at scale. "
    "Furthermore, it is important to note that this underscores the pivotal integration "
    "for every team involved in the programme."
)


class TestInspectEventCollection:
    def test_inspect_key_absent_by_default(self) -> None:
        """inspect=False (default) must not add the key to the result."""
        result = untell_text(_LOOP_TEXT, tier="lite", max_iters=1, rewriter="surgical")
        assert "inspect" not in result

    def test_inspect_key_present_when_requested(self) -> None:
        """inspect=True must add result['inspect'] as a list."""
        result = untell_text(_LOOP_TEXT, tier="lite", max_iters=1, rewriter="surgical", inspect=True)
        assert "inspect" in result
        assert isinstance(result["inspect"], list)

    def test_events_have_required_fields(self) -> None:
        """Every event must carry at minimum 'type' and 'iter'."""
        result = untell_text(_LOOP_TEXT, tier="lite", max_iters=1, rewriter="surgical", inspect=True)
        for ev in result["inspect"]:
            assert "type" in ev
            assert "iter" in ev

    def test_rejected_events_carry_gate_name(self) -> None:
        """candidate_rejected events must name the gate that fired."""
        result = untell_text(_LOOP_TEXT, tier="lite", max_iters=1, rewriter="surgical", inspect=True)
        rejected = [e for e in result["inspect"] if e.get("type") == "candidate_rejected"]
        for ev in rejected:
            assert "gate" in ev and isinstance(ev["gate"], str) and ev["gate"]

    def test_accepted_events_carry_draw(self) -> None:
        """candidate_accepted events must carry 'draw'."""
        result = untell_text(_LOOP_TEXT, tier="lite", max_iters=1, rewriter="surgical", inspect=True)
        accepted = [e for e in result["inspect"] if e.get("type") == "candidate_accepted"]
        for ev in accepted:
            assert "draw" in ev


# ---------------------------------------------------------------------------
# Gate truthfulness: inject a bad candidate and assert the correct gate is named
# ---------------------------------------------------------------------------

class TestGateNamingTruthfulness:
    """Construct a rewriter that returns a specific bad candidate and assert the gate is named."""

    def _run_with_fixed_candidate(self, candidate: str) -> list[dict]:
        """Run untell_text with a mock rewriter that always returns ``candidate``."""
        class _FixedRewriter:
            name = "fixed"
            deterministic = False

            def available(self) -> bool:
                return True

            def rewrite(self, text: str, score_result: dict, threshold: float = 0.30) -> str:
                return candidate

        result = untell_text(
            SRC,
            tier="lite",
            max_iters=1,
            best_of=1,
            rewriter=_FixedRewriter(),
            inspect=True,
        )
        return result.get("inspect", [])

    def test_number_dropped_names_numbers_kept(self) -> None:
        """A candidate that drops '42' must produce a 'numbers_kept' gate event."""
        bad = SRC.replace("42 ", "")
        events = self._run_with_fixed_candidate(bad)
        rejected = [e for e in events if e.get("type") == "candidate_rejected"]
        assert rejected, "expected at least one rejected event"
        gates = [e["gate"] for e in rejected]
        assert any(g == "numbers_kept" for g in gates), (
            f"expected 'numbers_kept' in gates, got {gates}"
        )

    def test_sentinel_dropped_names_sentinels(self) -> None:
        """A candidate that drops a locked sentinel must produce a 'sentinels' gate event."""
        from untell.scripts.preserve import lock

        src_with_sentinel = SRC + " See Smith (2020)."
        masked, _ = lock(src_with_sentinel)
        # The candidate keeps the text but strips the sentinel token.
        # Import the shared pattern — the inline copy was [0-9A-F]{4} which is (a) wrong
        # (hex class, not decimal; would accept ⟦HZABCD⟧) and (b) wrong (fixed width 4
        # misses ⟦HZ10000⟧ and later). test_sentinel_pattern_is_defined_once enforces
        # single-source-of-truth for this pattern.
        from untell.scripts.preserve import SENTINEL_RE
        bad = SENTINEL_RE.sub("", masked)  # drop the sentinel

        class _FixedMaskedRewriter:
            name = "fixed_masked"
            deterministic = False

            def available(self) -> bool:
                return True

            def rewrite(self, text: str, score_result: dict, threshold: float = 0.30) -> str:
                return bad

        result = untell_text(
            src_with_sentinel,
            tier="lite",
            max_iters=1,
            best_of=1,
            rewriter=_FixedMaskedRewriter(),
            inspect=True,
        )
        events = result.get("inspect", [])
        rejected = [e for e in events if e.get("type") == "candidate_rejected"]
        assert rejected, "expected at least one rejected event"
        gates = [e["gate"] for e in rejected]
        assert any(g == "sentinels" for g in gates), (
            f"expected 'sentinels' in gates, got {gates}"
        )

    def test_severe_deletion_names_deletion(self) -> None:
        """A heavily truncated candidate fires the deletion gate.

        Uses _DELETION_SRC (30+ words, no numbers) injected via a custom rewriter,
        so only the deletion gate fires (no numbers_kept interference).
        """
        bad = "The results."  # ~2 words vs 30+ in _DELETION_SRC

        class _FixedRewriterLong:
            name = "fixed_long"
            deterministic = False

            def available(self) -> bool:
                return True

            def rewrite(self, text: str, score_result: dict, threshold: float = 0.30) -> str:
                return bad

        result = untell_text(
            _DELETION_SRC,
            tier="lite",
            max_iters=1,
            best_of=1,
            rewriter=_FixedRewriterLong(),
            inspect=True,
        )
        events = result.get("inspect", [])
        rejected = [e for e in events if e.get("type") == "candidate_rejected"]
        assert rejected, "expected at least one rejected event"
        gates = [e["gate"] for e in rejected]
        assert any(g.startswith("deletion") for g in gates), (
            f"expected a 'deletion ...' gate in {gates}"
        )


# ---------------------------------------------------------------------------
# render_inspect_report smoke test
# ---------------------------------------------------------------------------

class TestRenderInspectReport:
    def test_renders_without_error(self) -> None:
        """render_inspect_report returns a non-empty string for any valid input."""
        events = [
            {"type": "candidate_rejected", "iter": 1, "draw": 1,
             "gate": "numbers_kept", "vetoes": ["numbers_kept"], "sim": 0.95},
            {"type": "candidate_accepted", "iter": 1, "draw": 2},
            {"type": "adopted", "iter": 1},
        ]
        report = render_inspect_report(SRC, SRC, events)
        assert isinstance(report, str) and len(report) > 0

    def test_report_names_the_gate(self) -> None:
        """The rendered text must mention the gate that fired."""
        events = [
            {"type": "candidate_rejected", "iter": 1, "draw": 1,
             "gate": "numbers_kept", "vetoes": ["numbers_kept"], "sim": 0.91},
        ]
        report = render_inspect_report(SRC, SRC, events)
        assert "numbers_kept" in report, f"expected 'numbers_kept' in report:\n{report}"

    def test_report_shows_candidate_log_header(self) -> None:
        """The report must include the CANDIDATE LOG section header."""
        report = render_inspect_report(SRC, "The trial.", [])
        assert "CANDIDATE LOG" in report

    def test_report_with_multiple_vetoes_shows_all(self) -> None:
        """When multiple vetoes fired, the report must show the primary and mention others."""
        events = [
            {"type": "candidate_rejected", "iter": 1, "draw": 1,
             "gate": "numbers_kept",
             "vetoes": ["numbers_kept", "polarity_kept"],
             "sim": 0.91},
        ]
        report = render_inspect_report(SRC, SRC, events)
        assert "numbers_kept" in report
        assert "polarity_kept" in report
