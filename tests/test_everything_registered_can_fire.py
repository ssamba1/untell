"""Anything registered must demonstrate it CAN fire, or it is dead code pretending to be coverage.

`tells` already has this guard, and it exists because six of its patterns were dead: a ``\\b``
written into a non-raw string became U+0008 and matched nothing, while the category still appeared
in every list and every count. Nothing failed. The catalogue simply reported zero for a tell it
could no longer see.

The same failure is available to every other registry in this repo, and each one is worse:

  * a **detector** that returns a constant contributes nothing to `max` but inflates the ensemble
    size the README advertises;
  * a **rewriter** that returns its input passes every quality check ever written, because output
    identical to the source cannot break anything;
  * a **meaning gate** that can never veto is a *false guarantee* — the one failure mode where
    silence is indistinguishable from success, and the thing users are asked to trust.

Each test below is a positive control: a crafted input the component must react to. Failing here
means the component is dead, not that the fixture is wrong — the fixtures are deliberately blatant.
"""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# Detectors
# ---------------------------------------------------------------------------

# Obvious cases. A detector that cannot separate THESE is not calibrated, it is broken.
_BLATANT_AI = (
    "Moreover, it is crucial to underscore the pivotal role of comprehensive frameworks in this "
    "domain. Furthermore, the system leverages robust methodologies to optimize operational "
    "efficiency across diverse sectors. Additionally, stakeholders must navigate the evolving "
    "landscape of digital transformation while fostering seamless collaboration. In conclusion, "
    "this multifaceted approach delivers transformative outcomes for all participants involved."
)
_BLATANT_HUMAN = (
    "I got the bus at half six and it was already packed. Some bloke had his bag on the seat "
    "next to him and wouldn't move it, so I stood the whole way. Rain the entire time. By the "
    "time I got in my shoes were soaked through and I'd missed the start of the match anyway. "
    "Nobody warned me the roadworks were back on that stretch. Typical."
)


def _live_detectors():
    from untell.detectors.base import all_detectors

    return [d for d in all_detectors() if d.available()]


def test_at_least_one_detector_is_live():
    """Guards the guard: an empty list would make every test below vacuously pass."""
    assert _live_detectors(), "no detector is available, so nothing below proves anything"


@pytest.mark.parametrize("name", [d.name for d in _live_detectors()])
def test_every_live_detector_separates_the_blatant_cases(name):
    """It need not be calibrated — it must not be CONSTANT.

    A detector returning the same number for both of these is contributing nothing to the ensemble
    while still being counted in it, which is exactly the shape the README's detector-count claim
    would hide.
    """
    detector = next(d for d in _live_detectors() if d.name == name)
    ai = detector.score(_BLATANT_AI)
    human = detector.score(_BLATANT_HUMAN)
    assert isinstance(ai, (int, float)) and isinstance(human, (int, float)), (
        f"{name} returned a non-numeric score"
    )
    assert ai != human, (
        f"{name} returns an identical score for blatant AI and blatant human prose — it is a "
        f"constant, not a detector"
    )


@pytest.mark.parametrize("name", [d.name for d in _live_detectors()])
def test_every_live_detector_stays_in_range(name):
    """A score outside [0, 1] silently dominates a `max` aggregation."""
    detector = next(d for d in _live_detectors() if d.name == name)
    for text in (_BLATANT_AI, _BLATANT_HUMAN):
        v = detector.score(text)
        assert 0.0 <= v <= 1.0, f"{name} returned {v}, outside [0, 1]"


# ---------------------------------------------------------------------------
# Rewriters
# ---------------------------------------------------------------------------

_CPU_REWRITERS = ["structural", "surgical", "composite", "targeted"]


@pytest.mark.parametrize("name", _CPU_REWRITERS)
def test_every_cpu_rewriter_can_change_text(name):
    """`targeted` was once measured changing 0 of 15 texts on the zero-dependency path, and
    `surgical` 16 of 30 with zero substitutions. Both looked healthy from the outside."""
    import random

    from untell.rewriter import get_rewriter
    from untell.scripts.score import score_text

    rw = get_rewriter(name)
    assert rw is not None, f"{name} is no longer registered"
    if not rw.available():
        pytest.skip(f"{name} unavailable here")

    pre = score_text(_BLATANT_AI, tier="lite")
    for seed in range(12):
        random.seed(seed)
        if rw.rewrite(_BLATANT_AI, pre).strip() != _BLATANT_AI.strip():
            return
    pytest.fail(f"{name} returned its input unchanged on blatant AI text across 12 seeds")


# ---------------------------------------------------------------------------
# Meaning gates — the ones where silence is indistinguishable from success
# ---------------------------------------------------------------------------

class TestEveryHedgeClassCanVeto:
    """A hedge class that can never fire is a fidelity guarantee that does not exist.

    One class was measurably over-firing earlier (`intention`, vetoing 20% of all candidates over a
    single bad synonym entry). The opposite failure is quieter: a class whose members no longer
    match anything simply stops protecting, and every rewrite sails through.
    """

    # source -> candidate pairs that DROP the named class entirely.
    DROPS = {
        "modality": ("The drug may cause drowsiness.", "The drug causes drowsiness."),
        "evidential": ("The results suggest a link.", "There is a link."),
        "frequency": ("It usually works.", "It works."),
        "quantifier": ("Some studies found an effect.", "Studies found an effect."),
        "degree": ("Revenue fell slightly.", "Revenue fell."),
        "intention": ("The company plans to expand.", "The company is expanding."),
    }

    def test_the_fixture_covers_every_class(self):
        from untell.scripts.hedges import _CLASSES

        assert set(self.DROPS) == set(_CLASSES), (
            "a hedge class has no positive control, so it could die unnoticed: "
            f"{set(_CLASSES) ^ set(self.DROPS)}"
        )

    @pytest.mark.parametrize("cls", sorted(DROPS))
    def test_class_vetoes_its_own_drop(self, cls):
        from untell.scripts.hedges import dropped_hedges

        source, candidate = self.DROPS[cls]
        assert cls in dropped_hedges(source, candidate), (
            f"the {cls} class did not notice its own removal — it is dead"
        )

    def test_a_faithful_reword_is_not_vetoed(self):
        """The complement. A gate that vetoes everything is as useless as one that vetoes nothing,
        and far more visible — this is the direction that was actually broken."""
        from untell.scripts.hedges import certainty_kept

        assert certainty_kept("The drug may cause drowsiness.", "The drug might cause sleepiness.")
        assert certainty_kept("Some studies found an effect.", "A few studies found an effect.")


class TestTheOtherGatesCanVeto:
    """Numerals, roles and the added-intensifier check, each on a violation it must catch."""

    def test_numerals_catches_a_changed_quantity(self):
        from untell.scripts.numerals import numbers_kept

        assert not numbers_kept("Revenue rose 12 percent.", "Revenue rose 21 percent.")
        assert numbers_kept("Revenue rose 12 percent.", "Revenue climbed 12 percent.")

    def test_roles_catches_a_swapped_argument(self):
        from untell.scripts.roles import available, role_swap

        if not available():
            pytest.skip("the role gate needs its optional model")
        assert role_swap("The company sued the regulator.", "The regulator sued the company.")

    def test_the_intensifier_check_catches_an_added_one(self):
        from untell.scripts.hedges import certainty_kept

        assert not certainty_kept("Revenue fell.", "Revenue collapsed dramatically.")

    def test_similarity_separates_a_paraphrase_from_a_different_claim(self):
        from untell.scripts.quality import similarity

        source = "Salt lowers the freezing point of water on the road surface."
        close = "Salt reduces the freezing point of water on roads."
        far = "The quarterly earnings report was delayed by two weeks."
        assert similarity(source, close) > similarity(source, far)
