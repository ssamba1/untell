"""The holdout arm's premises, which are the only things making its number mean anything.

Three ways this measurement can report a transfer figure that is not one, all of them silent:
the control is inside the tier the loop optimises (then it is not held out), the control cannot
tell human from AI on this corpus (then its movement is noise), or the in-sample column is pinned
by a saturated member so nothing cleared the tier and there is no transfer to ask about. The first
and third are mistakes this session actually made before the guards existed.

Fakes throughout — no model download, no loop. What is under test is the plumbing that decides
whether a number is publishable, not the detector.
"""

from __future__ import annotations

import os

import pytest

from eval import holdout


class _FakeDetector:
    """Scores by lookup, so a test can state exactly what the holdout believes."""

    name = "fake-holdout"

    def __init__(self, table: dict[str, float]):
        self.table = table
        self.seen: list[str] = []

    def score(self, text: str) -> float:
        self.seen.append(text)
        return self.table[text]


def _wire(monkeypatch, detector, pairs, rewritten):
    monkeypatch.setattr(holdout, "load_pairs", lambda dataset, n, min_words=60: pairs)
    monkeypatch.setattr(holdout, "_holdout_detector", lambda: detector)

    def fake_loop(text, **kw):
        pre, post, final = rewritten[text]
        return {"pre": {"max": pre}, "post": {"max": post}, "final": final, "similarity": 0.98}

    monkeypatch.setattr(holdout, "untell_text", fake_loop)


def test_the_control_may_not_be_inside_the_tier_it_is_controlling(monkeypatch):
    """UNTELL_ENABLE_RADAR=1 makes RADAR a selection target, so the arm has no subject."""
    monkeypatch.setenv("UNTELL_ENABLE_RADAR", "1")
    with pytest.raises(RuntimeError, match="no longer held out"):
        holdout._holdout_detector()


def test_the_gate_being_shut_is_what_makes_it_a_holdout(monkeypatch):
    """The mirror image: with the gate unset the detector loads and the run is legitimate."""
    monkeypatch.delenv("UNTELL_ENABLE_RADAR", raising=False)
    sentinel = object()
    monkeypatch.setattr("untell.detectors.radar.RadarDetector", lambda: sentinel)
    assert holdout._holdout_detector() is sentinel


def test_the_conviction_split_is_computed_from_the_pre_rewrite_belief(monkeypatch):
    """The finding this module exists for: gains concentrate where the holdout was unsure.

    Two documents. The holdout is certain about the first before anything happens and unmoved
    after; it is unsure about the second and drops. Both move the same amount in-sample, so an
    aggregate would call them equal — the split is what tells them apart.
    """
    detector = _FakeDetector({
        "ai-certain": 0.99, "out-certain": 0.98, "human-a": 0.05,
        "ai-unsure": 0.60, "out-unsure": 0.10, "human-b": 0.04,
    })
    _wire(
        monkeypatch, detector,
        pairs=[("human-a", "ai-certain"), ("human-b", "ai-unsure")],
        rewritten={"ai-certain": (0.99, 0.20, "out-certain"),
                   "ai-unsure": (0.99, 0.20, "out-unsure")},
    )

    result = holdout.run(n=2)

    assert result["by_conviction"]["confident"]["n"] == 1
    assert result["by_conviction"]["confident"]["mean_delta_holdout"] == pytest.approx(-0.01)
    assert result["by_conviction"]["confident"]["still_flagged"] == 1
    assert result["by_conviction"]["unsure"]["mean_delta_holdout"] == pytest.approx(-0.50)
    assert result["by_conviction"]["unsure"]["still_flagged"] == 0
    # Identical in-sample movement on both, which is the point.
    assert result["by_conviction"]["confident"]["mean_delta_tier"] == pytest.approx(
        result["by_conviction"]["unsure"]["mean_delta_tier"]
    )


def test_the_holdout_never_scores_a_candidate_the_loop_could_still_change(monkeypatch):
    """Scoring inside the loop would leak the control into selection through an ordering slip."""
    detector = _FakeDetector({"ai": 0.9, "out": 0.2, "human": 0.05})
    _wire(monkeypatch, detector, pairs=[("human", "ai")],
          rewritten={"ai": (0.9, 0.2, "out")})

    holdout.run(n=1)

    # Every call happens after the loop returned, on exactly three frozen strings per document.
    assert detector.seen == ["ai", "out", "human"]


def test_the_gate_is_open_while_scoring_and_shut_again_afterwards(monkeypatch):
    """The gate must be SHUT for the loop and OPEN for the control, and it is one env var.

    Shipped defect: this harness kept it shut throughout — right for the loop — so
    `RadarDetector.available()` was False, every score came back None, and the run died with
    "radar returned no scores". Every other test here injects a fake detector, which does not
    consult the gate, so all eight passed.
    """
    seen = []

    class _GateReadingDetector(_FakeDetector):
        def score(self, text):
            seen.append(os.environ.get("UNTELL_ENABLE_RADAR"))
            return super().score(text)

    monkeypatch.delenv("UNTELL_ENABLE_RADAR", raising=False)
    detector = _GateReadingDetector({"ai": 0.9, "out": 0.2, "human": 0.05})
    _wire(monkeypatch, detector, pairs=[("human", "ai")], rewritten={"ai": (0.9, 0.2, "out")})

    holdout.run(n=1)

    assert seen and all(v == "1" for v in seen), f"control scored with the gate at {set(seen)}"
    assert os.environ.get("UNTELL_ENABLE_RADAR") is None, "the caller's environment was left open"


def test_a_control_that_cannot_separate_says_so(monkeypatch):
    """A dead control makes every number uninterpretable rather than merely bad."""
    detector = _FakeDetector({"ai": 0.10, "out": 0.09, "human": 0.90})
    _wire(monkeypatch, detector, pairs=[("human", "ai")],
          rewritten={"ai": (0.9, 0.2, "out")})

    result = holdout.run(n=1)

    assert result["control"]["separates"] is False
    assert "DOES NOT SEPARATE" in holdout.render(result)


def test_a_pinned_in_sample_column_is_named_rather_than_printed_straight(monkeypatch):
    """MEASURED: with `mage` in the tier every document reads 1.0000 -> 1.0000 and nothing cleared."""
    detector = _FakeDetector({"ai": 0.9, "out": 0.5, "human": 0.05})
    _wire(monkeypatch, detector, pairs=[("human", "ai")],
          rewritten={"ai": (0.99999, 0.99999, "out")})

    result = holdout.run(n=1)

    assert result["in_sample"]["pinned"] is True
    assert "has no subject" in holdout.render(result)


def test_the_pinned_caveat_stays_silent_on_a_tier_that_moved(monkeypatch):
    """A caveat that fires on every run says nothing."""
    detector = _FakeDetector({"ai": 0.9, "out": 0.5, "human": 0.05})
    _wire(monkeypatch, detector, pairs=[("human", "ai")],
          rewritten={"ai": (0.99, 0.20, "out")})

    assert holdout.run(n=1)["in_sample"]["pinned"] is False


def test_no_paired_data_is_an_error_not_an_empty_table(monkeypatch):
    monkeypatch.setattr(holdout, "_holdout_detector", lambda: _FakeDetector({}))
    monkeypatch.setattr(holdout, "load_pairs", lambda dataset, n, min_words=60: [])
    assert "error" in holdout.run(n=4)


def test_the_result_names_the_corpus(monkeypatch):
    """Per-corpus reporting requires the corpus name to be in the result.

    Without it a caller cannot tell which corpus produced the numbers, and a function
    that is supposed to be run on hc3, raid, and mage all under the same interface
    would silently lose the provenance if the field were dropped.
    """
    detector = _FakeDetector({"ai": 0.9, "out": 0.2, "human": 0.05})
    _wire(monkeypatch, detector, pairs=[("human", "ai")], rewritten={"ai": (0.9, 0.2, "out")})

    for corpus in ("hc3", "raid", "mage"):
        result = holdout.run(dataset=corpus, n=1)
        assert result["config"]["dataset"] == corpus, (
            f"expected 'dataset' to be {corpus!r}, got {result['config'].get('dataset')!r}"
        )
        assert corpus in holdout.render(result)


def test_a_dead_control_does_not_print_transfer_numbers_as_findings(monkeypatch):
    """RADAR cannot separate HC3 human from AI — the render must say so, not a number.

    hc3_roberta is fine-tuned ON HC3 and sits in the selection tier, so the loop can
    trivially drive down HC3 in-sample scores. If RADAR also cannot separate on HC3, a
    positive-looking transfer figure would be produced entirely by a dead control —
    uninterpretable, not merely bad. The render gate is the last line of defence.
    """
    # Inverted scores: AI scores lower than human — control is dead on this corpus.
    detector = _FakeDetector({"ai": 0.12, "out": 0.11, "human": 0.85})
    _wire(monkeypatch, detector, pairs=[("human", "ai")],
          rewritten={"ai": (0.90, 0.20, "out")})

    result = holdout.run(dataset="hc3", n=1)

    assert result["control"]["separates"] is False
    rendered = holdout.render(result)
    assert "DOES NOT SEPARATE" in rendered
    # The corpus name must still be present so the reader knows WHICH corpus is dead.
    assert "hc3" in rendered
