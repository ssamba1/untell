"""Certainty retention — the rewrite must not claim more than the source did.

MEASURED before this module existed: seven of ten subtle strengthenings cleared the full meaning
gate (similarity + NLI + roles). None of them contradicts the source, and entailment — the min of
both directions — lands low but above the 0.005 floor:

    "The drug may cause drowsiness."  -> "The drug causes drowsiness."   PASSED
    "The results suggest a link."     -> "The results prove a link."     PASSED
    "She was accused of fraud."       -> "She committed fraud."          PASSED

Raising the entailment floor is the wrong lever — it was tuned to admit faithful register shifts,
which reword heavily. So this check is mechanical: the source hedged a claim somehow, the rewrite
must hedge it somehow. Any term from the same class counts.
"""

from __future__ import annotations

import json

import pytest

from untell.scripts import hedges
from untell.scripts.hedges import certainty_kept, dropped_hedges


class TestStrengtheningIsCaught:
    @pytest.mark.parametrize(
        ("source", "candidate", "cls"),
        [
            ("The drug may cause drowsiness.", "The drug causes drowsiness.", "modality"),
            ("The results suggest a link.", "The results prove a link.", "evidential"),
            ("Some studies found an effect.", "Studies found an effect.", "quantifier"),
            ("She was accused of fraud.", "She committed fraud.", "evidential"),
            ("It usually works.", "It always works.", "frequency"),
            ("The company plans to expand.", "The company is expanding.", "intention"),
            ("Revenue fell slightly.", "Revenue collapsed.", "degree"),
            ("Costs rose modestly.", "Costs skyrocketed.", "degree"),
            ("Output dipped a little.", "Output plunged.", "degree"),
        ],
    )
    def test_dropped_class_is_reported(self, source, candidate, cls):
        assert not certainty_kept(source, candidate)
        assert cls in dropped_hedges(source, candidate)


class TestFaithfulRewritesPass:
    """Swapping one hedge for another must never veto — otherwise the check starves the loop."""

    @pytest.mark.parametrize(
        ("source", "candidate", "label"),
        [
            ("The drug may cause drowsiness.", "The drug might make you drowsy.", "may->might"),
            ("Some studies found an effect.", "A handful of studies found an effect.", "some->handful"),
            ("The results suggest a link.", "The findings indicate a link.", "suggest->indicate"),
            ("It usually works.", "It tends to work most of the time.", "usually->tends"),
            ("The company plans to expand.", "The company aims to grow.", "plans->aims"),
            ("She was accused of fraud.", "She was allegedly involved in fraud.", "accused->allegedly"),
            ("Organizations use these tools.", "Companies rely on this stuff.", "no hedges present"),
            ("The build runs faster now.", "The build is quicker these days.", "plain paraphrase"),
            ("Revenue fell slightly.", "Revenue edged down.", "degree: verb carries smallness"),
            ("Revenue fell slightly.", "Revenue declined a fraction.", "degree: a fraction"),
            ("Revenue fell slightly.", "Revenue went down a touch.", "degree: a touch"),
            ("Revenue fell slightly.", "There was a small drop in revenue.", "degree: small"),
        ],
    )
    def test_no_false_veto(self, source, candidate, label):
        assert certainty_kept(source, candidate), f"{label}: {dropped_hedges(source, candidate)}"

    def test_real_rewriter_output_is_not_vetoed(self):
        """The check that decides whether this is safe to wire into the loop at all.

        Measured 0 vetoes over 18 rewrites (6 hedged sources x composite/structural/surgical). If a
        rewriter routinely dropped hedges this gate would reject its work and stall the loop.
        """
        from untell.rewriter import get_rewriter
        from untell.scripts.score import score_text

        sources = [
            "The results suggest that organizations may benefit from these tools.",
            "Some studies indicate that the approach usually improves outcomes.",
            "It appears that most users generally prefer the simpler interface.",
        ]
        vetoed = []
        for name in ("composite", "structural", "surgical"):
            rw = get_rewriter(prefer=name)
            if rw is None or not rw.available():
                continue
            for src in sources:
                out = rw.rewrite(src, score_text(src, tier="lite"), 0.30)
                if not certainty_kept(src, out):
                    vetoed.append((name, dropped_hedges(src, out), out))
        assert not vetoed, f"rewriter output would be vetoed: {vetoed}"


class TestHedgesCLI:
    def test_help_exits_zero(self, capsys):
        assert hedges.main(["--help"]) == 0
        assert "usage" in capsys.readouterr().out.lower()

    def test_missing_args_is_usage_error(self):
        assert hedges.main([]) == 2
        assert hedges.main(["only one"]) == 2

    def test_exit_code_matches_kept_field(self, capsys):
        for a, b in [
            ("The drug may cause drowsiness.", "The drug causes drowsiness."),
            ("The drug may cause drowsiness.", "The drug might make you drowsy."),
        ]:
            code = hedges.main([a, b])
            payload = json.loads(capsys.readouterr().out)
            assert code == (0 if payload["kept"] else 1)

    def test_exit_codes_align_with_the_other_gates(self):
        from untell.scripts import entailment, numbers, roles

        assert hedges.main([]) == numbers.main([]) == entailment.main([]) == roles.main([]) == 2


def test_meaning_gate_rejects_strengthening_end_to_end():
    from untell.scripts.entailment import meaning_preserved
    from untell.scripts.quality import similarity

    src, bad = "The drug may cause drowsiness.", "The drug causes drowsiness."
    good = "The drug might make you drowsy."
    assert not meaning_preserved(src, bad, similarity(src, bad), strict_sim_bar=0.76)
    assert meaning_preserved(src, good, similarity(src, good), strict_sim_bar=0.76)
