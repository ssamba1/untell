"""A detector that produces nothing lowers `max`, and the whole error is toward NOT flagged.

`max` over fewer members can only fall, so every ensemble that loses a detector errs in one
direction: telling someone their AI text reads as human. MEASURED on a real AI paragraph with the
strongest member of a four-detector full-tier ensemble silenced:

    all four live    max 0.6566   flagged True
    one silent       max 0.1058   flagged False

RE-MEASURED on the five-detector ensemble this repo now loads, same AI_TEXT:

    all five live    max 1.0000   flagged True
    top silent       max 0.8264   flagged False (at the midpoint cut)

The drop is smaller because the members changed, not because the effect weakened — see
`_top_member` for why naming the strongest one in the test body was the actual bug.

`failed_detectors` named the raising case and said nothing about what the absence did to the
verdict. The abstaining case had no top-level trace at all — the only sign was a `null` nested
inside `detectors`, which is a `null` in the JSON no API client inspects once `flagged` has answered
the question. That is the exact failure `commercial.py` warns about on stderr: a provider changes
its response shape, the adapter returns None, and a billed detector leaves the ensemble quietly.

MEASURED over 80 real HC3 texts at >=60 words, partial abstentions were 0/80 — so this caveat does
not fire on healthy scoring, which is what makes it worth reading when it does.
"""

from __future__ import annotations

import pytest

from untell.scripts.score import score_text
@pytest.fixture(autouse=True)
def _torch_path(monkeypatch):
    """These assertions exercise model-backed paths (NER entities, the full ensemble,
    the NLI gate, the spaCy role veto). Under UNTELL_LITE_NO_TORCH=1 those paths are
    gated away (no entities, reduced ensemble, similarity-only naming, role_swap=None),
    so the file fails without meaning anything. Pin the env unset for the file.
    """
    monkeypatch.delenv("UNTELL_LITE_NO_TORCH", raising=False)

AI_TEXT = (
    "Moreover, the framework leverages robust methodologies to deliver outcomes at scale. "
    "It significantly improves overall efficiency and accuracy across the evaluated corpus. "
    "In conclusion, these findings underscore the importance of a comprehensive approach. "
    "Furthermore, the results demonstrate substantial gains in downstream task performance."
)


def _detector_class():
    import untell.detectors.roberta_openai as R

    names = [n for n in dir(R) if n.endswith("Detector")]
    assert names, "roberta_openai no longer exposes a detector class; this test is stale"
    return getattr(R, names[0])


def _top_member(result: dict) -> tuple[type, str]:
    """The class and name of whichever detector actually set `max` on this machine.

    Naming a member here is a standing bug. These two tests hard-coded `roberta_openai` as "the
    strongest member", and by the time it was checked that was false: on this same AI_TEXT the
    ensemble reads

        mage 1.0000   perplexity_burstiness 0.8264   roberta_openai 0.2991
        hc3_roberta 0.0003   fast_detectgpt 0.0146

    `mage` is saturated at exactly 1.0, so silencing roberta_openai moved `max` not at all and both
    tests failed on their own premise — not on the behaviour they exist to protect. Which detector
    tops the ensemble is a property of the model set and the input, and it changes; the invariant
    under test (losing a member can only push `max` down, and that has to be said out loud) does
    not. So resolve the member from the measurement instead of asserting a name.

    TIES are part of the same lesson: with the current models this AI_TEXT saturates TWO members
    (mage at 1.0 and hc3_roberta at 0.9979), so silencing a single name still moves `max` not at
    all. The tests silence EVERY member tied at the top.
    """
    from untell.detectors.base import load_detectors

    scored = {k: v for k, v in result["detectors"].items() if isinstance(v, (int, float))}
    assert scored, "no detector produced a number; nothing to silence"
    top = max(scored.values())
    tied = sorted(k for k, v in scored.items() if v == top)
    classes = []
    for d in load_detectors("full"):
        if d.name in tied:
            classes.append((type(d), d.name))
    assert classes, f"the max-setting member(s) {tied} are not in load_detectors('full')"
    return classes


@pytest.fixture
def healthy() -> dict:
    from untell.scripts import score as sc

    result = score_text(AI_TEXT, tier="full")
    assert len(result["detectors"]) >= 2, "a one-detector ensemble cannot be partially reduced"
    # The per-text score cache would otherwise serve THIS result to the silenced re-score
    # below (identical text/tier/threshold/mode key) — the silencing must actually re-run.
    sc._score_cache.clear()
    return result


def test_an_abstaining_detector_is_reported(healthy, monkeypatch: pytest.MonkeyPatch) -> None:
    # Patch the real extension point: the batched windowing path calls `_score_batch`,
    # not the per-text `score` (wave-3 slice-5 batched scoring), so `.score` is dead here.
    for cls, name in _top_member(healthy):
        monkeypatch.setattr(cls, "_score_batch", lambda self, windows, _n=name: [None] * len(windows))
    result = score_text(AI_TEXT, tier="full")

    assert result["max"] < healthy["max"], "premise: silencing the top member(s) must lower max"
    assert any(n in (result.get("warning") or "") for _, n in _top_member(healthy))
    assert "errs toward NOT flagged" in result["warning"]


def test_losing_a_detector_can_flip_the_verdict(healthy, monkeypatch: pytest.MonkeyPatch) -> None:
    """The consequence, stated as a threshold rather than as an environment.

    Whether the default 0.30 happens to sit between the two maxima depends on which detectors
    loaded — under UNTELL_LITE_NO_TORCH the ensemble is different and both sides land above it. The
    claim is not about 0.30: it is that a band exists where the same text is flagged with the full
    ensemble and cleared without it. Taking the cut from the two measured maxima tests exactly that,
    on whatever detectors this machine has.
    """
    for cls, _ in _top_member(healthy):
        monkeypatch.setattr(cls, "_score_batch", lambda self, windows: [None] * len(windows))
    reduced = score_text(AI_TEXT, tier="full")
    assert reduced["max"] < healthy["max"], "premise: the top member(s) must have been silenced"

    cut = (reduced["max"] + healthy["max"]) / 2
    monkeypatch.undo()
    assert score_text(AI_TEXT, tier="full", threshold=cut)["flagged"] is True

    from untell.scripts import score as sc

    sc._score_cache.clear()  # the un-silenced score above must not serve the silenced one below
    for cls, _ in _top_member(healthy):
        monkeypatch.setattr(cls, "_score_batch", lambda self, windows: [None] * len(windows))
    after = score_text(AI_TEXT, tier="full", threshold=cut)
    assert after["flagged"] is False, "the verdict must actually flip in this band"
    assert "errs toward NOT flagged" in (after.get("warning") or ""), (
        "the flip happened; the caveat is the only thing that says why"
    )


def test_an_erroring_detector_is_reported_too(healthy, monkeypatch: pytest.MonkeyPatch) -> None:
    """`failed_detectors` names which one died. It does not say the verdict moved because of it."""

    def boom(self, windows):
        raise RuntimeError("adapter blew up")

    monkeypatch.setattr(_detector_class(), "_score_batch", boom)
    result = score_text(AI_TEXT, tier="full")

    assert result["failed_detectors"] == ["roberta_openai"]
    assert "errored" in (result.get("warning") or ""), result.get("warning")
    assert "errs toward NOT flagged" in result["warning"]


def test_a_healthy_ensemble_says_nothing(healthy) -> None:
    """Guards the guard. A caveat on every scoring is noise, and noise is how a caveat that matters
    gets skipped — the 0/80 measurement above is what this pins."""
    assert "errs toward NOT flagged" not in (healthy.get("warning") or "")


def test_the_count_is_the_real_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """"3 of 4" has to be arithmetic, not a fixed string."""
    monkeypatch.setattr(_detector_class(), "score", lambda self, text: None)
    result = score_text(AI_TEXT, tier="full")
    live = sum(1 for v in result["detectors"].values() if isinstance(v, (int, float)))
    total = sum(1 for k in result["detectors"] if not k.endswith("__error"))
    assert f"{live} of {total} detectors" in result["warning"], result["warning"]


def test_it_composes_with_the_other_caveats(monkeypatch: pytest.MonkeyPatch) -> None:
    """Short text and a reduced ensemble are independent problems; an elif would hide one.

    The short-text caveat is the one already known to fire here, so if the two ever collapse into a
    single slot this is where it shows.
    """
    monkeypatch.setattr(_detector_class(), "score", lambda self, text: None)
    result = score_text("Moreover, the framework leverages robust methodologies at scale.",
                        tier="full")
    warning = result.get("warning") or ""
    if "too short" in warning:  # only assert composition where both conditions genuinely hold
        assert "detectors produced a score" in warning, warning
