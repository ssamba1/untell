"""`detector_audit` answers "does this detector discriminate", not "can a rewrite move it".

Driven with synthetic detectors whose correct verdict is known, so it needs no model download. Four
shapes, four verdicts, all correct:

    perfect    (1.0 on AI, 0.0 on human)   OK_SEPARATED   auroc 1.0
    inverted   (0.0 on AI, 1.0 on human)   INVERTED       auroc 0.0   <- not mistaken for good
    constant   (0.5 always)                DEAD           range 0.0
    saturated  (1.0 always)                DEAD           range 0.0

The last two are the failure modes this repository has actually been bitten by, and the tool names
both.

**The fifth shape is the one worth writing down.** A detector fine-tuned on the corpus being scored
separates it perfectly and has no headroom left on the AI side — `hc3_roberta` on HC3 runs human 0.08
against AI 0.9992, with the entire AI spread across 15 documents measuring 1.2e-05. Audited:

    verdict OK_SEPARATED   auroc 1.0   gap 0.9192   range 0.9192

Correct, and it is why a clean detector audit never surfaced the pinning that took four results to
find. Separation and improvement headroom are different quantities: this tool measures the first, the
loop needs the second, and a detector can be flawless at one while offering none of the other.
"""

from __future__ import annotations

import logging

import pytest

from eval.detector_audit import audit_detector

HUMAN = [
    "I drove up on Friday and the traffic was awful past the junction near the bridge.",
    "The cat sat on the mat and then went outside to look at the birds this morning.",
    "I tried the recipe twice and cut the milk by a third the second time around.",
]
AI = [
    "Moreover, the framework leverages a robust approach to deliver transformative outcomes.",
    "Furthermore, it is important to note that this underscores the pivotal integration.",
    "In conclusion, organizations must harness these seamless and comprehensive solutions.",
]
PROBES = (HUMAN, AI)


class _Fake:
    """The minimum a detector must expose. `available()` is part of it — omitting it made the tool
    report `AVAIL_ERR:AttributeError`, which is the honest answer and worth keeping in mind: this
    tool does not guess when a detector will not answer."""

    tier = "full"
    name = "probe"

    def __init__(self, fn) -> None:
        self._fn = fn

    def available(self) -> bool:
        return True

    def score(self, text: str) -> float:
        return self._fn(text)


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


def _verdict(fn) -> dict:
    return audit_detector("probe", _Fake(fn), PROBES)


def test_a_working_detector_is_reported_working() -> None:
    r = _verdict(lambda t: 1.0 if t in AI else 0.0)
    assert r["verdict"] == "OK_SEPARATED" and r["auroc"] == 1.0


def test_an_inverted_detector_is_not_mistaken_for_a_good_one() -> None:
    """The dangerous confusion: perfect separation in the wrong direction is still perfect
    separation, and an audit reading only |AUROC - 0.5| would call it excellent."""
    r = _verdict(lambda t: 0.0 if t in AI else 1.0)
    assert r["verdict"] == "INVERTED" and r["auroc"] == 0.0


def test_a_constant_detector_is_dead() -> None:
    r = _verdict(lambda t: 0.5)
    assert r["verdict"] == "DEAD" and r["range"] == 0.0


def test_a_saturated_detector_is_dead() -> None:
    """This shape has shipped here: a detector returning exactly 1.0 for everything disabled
    candidate selection in the default rewriter."""
    r = _verdict(lambda t: 1.0)
    assert r["verdict"] == "DEAD" and r["range"] == 0.0


def test_separation_is_not_headroom() -> None:
    """The limit of the question this tool asks, asserted so nobody reads a clean audit as proof the
    loop can make progress. `hc3_roberta` on HC3 has exactly this shape and is reported healthy."""
    r = _verdict(lambda t: 0.9992 if t in AI else 0.08)
    assert r["verdict"] == "OK_SEPARATED"
    assert r["ai_mean"] > 0.99, "premise: no headroom left above the AI mean"


def test_a_detector_that_will_not_answer_is_not_guessed_at() -> None:
    """Dropping `available()` must report the failure, not a verdict derived from nothing."""

    class _Broken:
        tier = "full"
        name = "probe"

        def score(self, text: str) -> float:
            return 0.5

    assert "ERR" in audit_detector("probe", _Broken(), PROBES)["verdict"]
