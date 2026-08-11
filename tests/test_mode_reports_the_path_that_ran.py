"""`mode()` answered which path *would* run. The verdict depends on which one *did*.

`perplexity_burstiness` has two scoring paths whose false-positive rates differ by 11.5x (gpt2 6.0%,
stdlib 69.0% on 100 held-out HC3 pairs). `score._verdict_threshold` reads `detector_modes` and
raises the cut from 0.30 to 0.45 when the stdlib path is the whole verdict, because the average
HUMAN paragraph scores 0.399 on it.

`mode()` returned `"gpt2" if torch is importable`, which is a prediction, not a record. The two
separate on exactly the failure the detector already warns about: torch imports, the model raises at
scoring time, the stdlib heuristic produces the number, and the field says the model did. MEASURED
on a human paragraph with the full path forced to raise:

    before  mode=gpt2    cut 0.30   max 0.4044   FLAGGED
    after   mode=stdlib  cut 0.45   max 0.4044   not flagged

So the guard that exists to stop humans being accused was switched off by the one failure it was
there to cover, and the error landed on the accusing side.
"""

from __future__ import annotations

import pytest

from untell.detectors.perplexity_burstiness import PerplexityBurstinessDetector, lite_score
from untell.scripts.score import score_text

# Real human prose: first person, contractions, a fragment, uneven sentence lengths.
HUMAN = (
    "I never really planned to end up here, honestly. My brother had a spare room and I had two "
    "boxes and a bike, so that was that. The first winter was rough. But you get used to the "
    "noise, and then one day you notice you'd miss it. Funny how that works."
)


@pytest.fixture
def torch_ready_but_broken(monkeypatch: pytest.MonkeyPatch):
    """torch importable, model raises at scoring time — OOM, a corrupt cache, a version bump."""

    def boom(self, text):
        raise RuntimeError("simulated CUDA OOM")

    monkeypatch.setattr(PerplexityBurstinessDetector, "_torch_ready", lambda self: True)
    monkeypatch.setattr(PerplexityBurstinessDetector, "_full_score", boom)


def test_the_fallback_is_reported_as_the_path_it_is(torch_ready_but_broken) -> None:
    d = PerplexityBurstinessDetector()
    assert d.mode() == "gpt2", "before scoring, the prediction is all there is — and torch is ready"
    d.score(HUMAN)
    assert d.mode() == "stdlib", "the stdlib heuristic produced the score; the field must say so"


def test_a_healthy_full_path_still_reports_gpt2(monkeypatch: pytest.MonkeyPatch) -> None:
    """Guards the guard: reporting stdlib unconditionally would satisfy the test above and would
    raise the verdict cut to 0.45 on the well-calibrated path, under-flagging real AI."""
    monkeypatch.setattr(PerplexityBurstinessDetector, "_torch_ready", lambda self: True)
    monkeypatch.setattr(PerplexityBurstinessDetector, "_full_score", lambda self, text: 0.42)
    d = PerplexityBurstinessDetector()
    d.score(HUMAN)
    assert d.mode() == "gpt2"


def test_the_two_paths_disagree_enough_for_this_to_matter(monkeypatch: pytest.MonkeyPatch) -> None:
    """The premise, measured rather than assumed. If the paths agreed on this fixture the tests
    below would pass for the wrong reason — a fixture where they coincide proves nothing about
    which label was attached."""
    monkeypatch.setattr(PerplexityBurstinessDetector, "_torch_ready", lambda self: False)
    stdlib = PerplexityBurstinessDetector().score(HUMAN)
    assert stdlib == pytest.approx(lite_score(HUMAN))
    assert stdlib > 0.30, (
        f"the stdlib path scores this human paragraph at {stdlib}, below the 0.30 cut — the "
        "fixture no longer reaches the band the 0.45 guard protects"
    )


def test_a_human_paragraph_is_not_accused_when_the_model_dies(torch_ready_but_broken) -> None:
    """The consequence, end to end. This is the assertion that would have failed before the fix."""
    result = score_text(HUMAN, tier="lite")
    assert result["detector_modes"]["perplexity_burstiness"] == "stdlib"
    assert result["verdict_threshold"] == pytest.approx(0.45), (
        "the stdlib path is the whole verdict here, so the cut must rise — otherwise the 69% "
        "false-positive rate is judged at a threshold calibrated for the 6% one"
    )
    assert result["max"] > 0.30, "premise: this would have been flagged at the unraised cut"
    assert result["flagged"] is False


def test_two_detectors_do_not_overwrite_each_other(monkeypatch: pytest.MonkeyPatch) -> None:
    """`_last_path` is declared on the class, so a class-level assignment would make one instance's
    fallback rewrite every other instance's label."""
    monkeypatch.setattr(PerplexityBurstinessDetector, "_torch_ready", lambda self: True)
    healthy = PerplexityBurstinessDetector()
    monkeypatch.setattr(PerplexityBurstinessDetector, "_full_score", lambda self, text: 0.42)
    healthy.score(HUMAN)

    broken = PerplexityBurstinessDetector()
    monkeypatch.setattr(
        PerplexityBurstinessDetector,
        "_full_score",
        lambda self, text: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    broken.score(HUMAN)

    assert broken.mode() == "stdlib"
    assert healthy.mode() == "gpt2", "one instance's fallback leaked onto another's record"
