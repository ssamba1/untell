"""`humanness` returns 50.0 to mean "I cannot tell", and 50.0 is also a score it can compute.

FOUND while measuring how much the score moves with paste length. One 100-word HC3 answer came back
at exactly 50.0 with the detector ensemble at **P(AI) = 0.9992** — the strongest possible AI signal,
reported as a dead tie. Nothing had abstained. The three terms simply summed there: 0.50 x 0.9992
of detector, near-zero tells, healthy burstiness.

That collides with every other use of the number. `humanness` returns a literal 50.0 for empty text,
for text under `_MIN_WORDS_FOR_SIGNAL`, and for text in a script the catalogue cannot read, and the
docstring calls it "the same 'cannot tell' answer empty text gets". A caller holding the bare float
cannot tell abstention from a computed tie.

**No shipped code compares against it** — checked across `untell/` and `eval/`; only tests do, and
they assert that abstention returns 50.0 rather than reading 50.0 as abstention. So this is a
documented ambiguity, not a live defect, and this file exists to keep it that way: anything that
starts treating `== 50.0` as "abstained" is wrong for the reason measured here.
"""

from __future__ import annotations

import logging

import pytest

import untell.humanness as hm
from untell.humanness import _W_DETECTOR, classification, humanness
from untell.scripts.score import _STDLIB_PERPLEXITY_VERDICT_THRESHOLD

CLEAN = (
    "Salt lowers the freezing point of water, which is why councils spread it on roads once the "
    "forecast turns. It stops working somewhere around minus nine degrees, and below that you need "
    "something else entirely. Most mixes add a bit of grit so the surface gains some traction too, "
    "and the lorries go out overnight when there is less traffic to work around."
)


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


def _with_detector_max(monkeypatch, value: float) -> None:
    monkeypatch.setattr(
        hm, "score_text", lambda text, tier="full": {"max": value, "scored": True, "warning": None}
    )


def test_a_confident_ai_verdict_can_land_on_the_abstention_value(monkeypatch) -> None:
    """The measured collision, reconstructed deterministically instead of quoted.

    Solve for the detector reading that puts the composite exactly on 50.0 given this text's own
    tells and burstiness, then check the detector really is calling it AI when it gets there."""
    _with_detector_max(monkeypatch, 0.0)
    without_detector = humanness(CLEAN)
    needed = (without_detector / 100.0 - 0.5) / _W_DETECTOR
    # Anchored on the shipped verdict bar rather than a round number: the point is that the
    # detector is calling this text AI, loudly, at the reading that produces a tie. The corpus case
    # that found this needed 0.9992 because its tells were near zero; this text carries a small
    # penalty of its own, so it gets there sooner.
    assert _STDLIB_PERPLEXITY_VERDICT_THRESHOLD < needed <= 1.0, (
        f"premise: the collision must sit above the verdict bar ({needed})"
    )

    _with_detector_max(monkeypatch, needed)
    assert humanness(CLEAN) == pytest.approx(50.0, abs=0.05)


def test_the_abstentions_return_the_same_number(monkeypatch) -> None:
    """The other half of the collision. These are the inputs the docstring means by "cannot tell"."""
    _with_detector_max(monkeypatch, 0.0)
    assert humanness("") == 50.0
    assert humanness("   ") == 50.0
    assert humanness("Hi there") == 50.0


def test_the_shared_value_reads_as_mixed_either_way() -> None:
    """Which is the saving grace: the band is the same honest "mixed" whether the 50.0 was computed
    or abstained, so the collision misleads a caller reading the float, not one reading the band."""
    assert classification(50.0) == "mixed"


def test_nothing_shipped_reads_fifty_as_abstention() -> None:
    """The invariant that makes the ambiguity tolerable. If a caller ever branches on `== 50.0`, the
    confident-AI case above walks straight into it."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    offenders = []
    for path in list((root / "untell").rglob("*.py")) + list((root / "eval").rglob("*.py")):
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#", 1)[0]
            if ("== 50.0" in code or "!= 50.0" in code) and "humanness" in code.lower():
                offenders.append(f"{path.relative_to(root)}:{n}")
    assert not offenders, offenders
