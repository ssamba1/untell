"""The stdlib lite warning must warn about the error that costs something.

It used to say only "treat a flag as a prompt to re-run at --tier full". That is the harmless
direction: a false flag costs the user one re-run. The expensive direction is the reverse — this
path calling AI text clean, after which nobody re-runs anything.

MEASURED, lite verdict against full verdict, each at its own published verdict_threshold:

    corpus        full flags   lite clears it anyway
    HC3 (n=30)      30/30           3  = 10%
    RAID (n=30)     30/30          21  = 70%

Every miss sat against a full-tier score of 1.000. Both corpora are named in the warning because
the rate swings 7x between them; a single figure would be a property of one corpus.

These tests assert the warning's CONTENT, not the rates — re-measuring live would need the full
ensemble and a corpus download. What is checked mechanically is that the sentence covers both
directions and cannot silently revert to the flag-only form.
"""
from __future__ import annotations

import pytest

from untell.scripts.score import score_text

AI_TEXT = (
    "Furthermore, artificial intelligence has fundamentally transformed numerous industries "
    "across the global economy. Moreover, organizations increasingly leverage these advanced "
    "technologies to optimize operational efficiency and drive meaningful innovation forward. "
    "Overall, the transformative impact of these systems continues to expand across various "
    "sectors, reshaping how enterprises approach strategic decision making and long term "
    "planning in an increasingly competitive marketplace environment today."
)


@pytest.fixture
def lite_warning(monkeypatch) -> str:
    """The warning from the one configuration it is written for: stdlib path, sole detector."""
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
    result = score_text(AI_TEXT, tier="lite")

    if result.get("detector_modes", {}).get("perplexity_burstiness") != "stdlib":
        pytest.skip("torch is importable here, so the stdlib path did not run")
    warning = result.get("warning")
    assert warning, "the stdlib lite path must carry a warning; it is the weakest verdict untell has"
    return warning


def test_the_warning_names_the_false_clear_direction(lite_warning):
    lowered = lite_warning.lower()
    assert "clear" in lowered, (
        "the warning covers only false flags; a user whose AI text this path called clean is the "
        "one who never re-runs and never finds out"
    )


def test_the_warning_does_not_stop_at_prompting_on_a_flag(lite_warning):
    """The flag-only sentence is the exact wording this test exists to prevent reverting to."""
    assert "flag OR a clear" in lite_warning or "flag or a clear" in lite_warning, (
        f"warning still advises re-running on a flag alone: {lite_warning!r}"
    )


def test_the_warning_states_both_corpora_because_the_rate_swings(lite_warning):
    """One number here would be true of one corpus. HC3 10% and RAID 70% are 7x apart."""
    assert "HC3" in lite_warning
    assert "RAID" in lite_warning, (
        "only HC3 is quoted; the same weakness is 70% on RAID, and a reader given the 10% figure "
        "alone would take the low end as the property of the tier"
    )


def test_the_warning_still_carries_the_human_side_numbers(lite_warning):
    """The false-positive direction was already documented — adding the other must not drop it."""
    assert "HUMAN" in lite_warning
    assert "0.45" in lite_warning and "0.30" in lite_warning, (
        "the two thresholds answer different questions and the warning has to keep saying so"
    )


def test_the_warning_is_absent_when_other_detectors_decided_the_verdict(monkeypatch):
    """With the full ensemble live, the stdlib heuristic does not own the max — do not scold."""
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
    result = score_text(AI_TEXT, tier="full")
    if len(result.get("detectors", {})) <= 1:
        pytest.skip("full tier produced a single detector here; nothing to distinguish")
    assert "weak evidence in both directions" not in (result.get("warning") or "").lower()
