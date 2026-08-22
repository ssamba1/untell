"""A caveat that fires once per process reaches one document and no others.

`humanness` returns a bare float, and its own comments record the consequence: "This surface
returns a bare float, so a log line is the only channel it has." That is true at a terminal, for
one document. It is false for the two ways this function is actually used at scale.

MEASURED before the fix, five sub-threshold texts scored in one process:

    5 documents  ->  5 scores of 50.0  ->  1 caveat

Documents 2..5 got the same fiat number with nothing attached. The same shape costs more in a
long-lived server: request 1 carries the caveat, every later request is silent, and the warning
lands in the operator's log rather than with the caller holding the number.

The gap was worst exactly where it matters most. `undetermined_reason` covers only the three cases
where the score is WITHHELD; it deliberately does not cover the 5-to-40-word band, because there
the score is returned. That band is the one with measured harm on it — AUROC 0.694 against 0.978
at full length, and 0 of 30 genuine human texts reaching a human band. The caveat a caller most
needs was the caveat with no accessor.

The warn-once logging is deliberate — a CLI walking a directory should not repeat itself — so it
is unchanged. What is added is a second channel that is per document.
"""

from __future__ import annotations

import logging

import pytest

from untell import humanness as H

# Above the five-word floor, below the forty-word bar: the band where the number is returned and
# does not separate the classes.
BAND_TEXT = (
    "This is a sentence of moderate length written to sit above the five word floor but "
    "comfortably below the forty word bar where the bands stop separating."
)
CHINESE = "这是一段中文文字，用来测试检测器的行为，看看它会不会给出一个虚假的判断结果。"


@pytest.fixture(autouse=True)
def _reset_warn_once():
    """Every case starts with the process flags unspent.

    Without this the second test to run finds the flag already set by the first and reads a
    correctly-suppressed log line as a defect — the same trap `test_every_caveat_can_be_reached`
    documents.
    """
    for flag in (
        "_WARNED_TOO_SHORT",
        "_WARNED_SHORT_BAND",
        "_WARNED_UNSUPPORTED_LANGUAGE",
        "_WARNED_WEAK_PATH",
        "_WARNED_INVISIBLE",
        "_WARNED_EMPTY",
    ):
        assert hasattr(H, flag), f"{flag} vanished — this fixture is guarding nothing"
        setattr(H, flag, False)
    yield


def test_every_document_in_a_batch_carries_its_own_caveat(caplog):
    """The defect, stated as the measurement that found it: 5 documents, 1 caveat."""
    batch = ["too short", "also brief", "third one here", "fourth tiny text", "fifth wee one"]

    with caplog.at_level(logging.WARNING):
        results = [H.humanness_with_caveats(t, tier="lite") for t in batch]

    assert [score for score, _ in results] == [50.0] * len(batch), "premise: all abstain alike"
    carried = [caveats for _, caveats in results if caveats]
    assert len(carried) == len(batch), (
        f"only {len(carried)} of {len(batch)} documents carried a caveat"
    )
    # The log is unchanged: still once, which is why it could never have done this job.
    assert sum("shorter than" in r.message for r in caplog.records) == 1


def test_the_band_caveat_is_reachable_as_data_and_not_only_as_a_log_line():
    """The 5-to-40-word band: score returned, AUROC 0.694, and previously no accessor.

    `undetermined_reason` returns None here — correctly, since nothing is withheld — so before
    this it was the one caveat a programmatic caller could not obtain at all.
    """
    assert H.undetermined_reason(BAND_TEXT) is None, "premise: this text is scored, not withheld"

    score, caveats = H.humanness_with_caveats(BAND_TEXT, tier="lite")

    assert 0.0 <= score <= 100.0
    assert any("does not separate the classes" in c for c in caveats), caveats
    assert any("0 of 30" in c for c in caveats), "the measurement must travel with the caveat"


def test_empty_text_is_told_it_is_empty_rather_than_told_nothing():
    """FOUND wiring this up: the empty branch returned 50.0 in total silence.

    `humanness` grew an early `if not text or not text.strip(): return 50.0` ABOVE its call to
    `undetermined_reason`, so the function that exists to keep the abstention reasons in one place
    never saw the empty case. `undetermined_reason("")` said "empty" and `humanness("")` said
    nothing — drift in the branch that function was written to prevent drift in.
    """
    assert H.undetermined_reason("") == "empty", "premise: the reason exists"

    score, caveats = H.humanness_with_caveats("", tier="lite")

    assert score == 50.0
    assert caveats, "empty text abstained with no caveat at all"
    assert "empty" in caveats[0]
    # And it must not be told its script is unsupported, which is a claim about no characters.
    assert "English-only catalogue" not in caveats[0]


def test_an_unreadable_script_still_gets_the_language_caveat_not_the_empty_one():
    """The mirror image, so the new branch cannot swallow the case next to it."""
    score, caveats = H.humanness_with_caveats(CHINESE, tier="lite")

    assert score == 50.0
    assert any("English-only catalogue" in c for c in caveats), caveats
    assert not any("the text is empty" in c for c in caveats)


def test_a_qualified_number_says_so_and_an_unqualified_one_stays_quiet():
    """An empty list has to mean something, or the channel is noise.

    A caveat list that is never empty carries no information — the same reasoning
    `test_the_pinned_caveat_stays_silent_on_a_tier_that_moved` records for the holdout.
    """
    long_clean = " ".join(
        [
            "The bus was late again this morning and I stood in the rain reading the timetable",
            "somebody had taped to the shelter, which had the wrong times on it anyway.",
            "By the time it came I had given up and started walking, and of course it passed me",
            "two streets later with plenty of empty seats going by in the window.",
            "I got to the office wet enough that someone asked if I had swum in.",
        ]
    )
    assert len(long_clean.split()) >= H._MIN_WORDS_FOR_A_BAND, "premise: clears the band bar"

    _, caveats = H.humanness_with_caveats(long_clean, tier="full")

    assert caveats == [], f"a clean full-tier document should carry nothing: {caveats}"


def test_the_score_is_identical_whether_or_not_caveats_are_collected():
    """Collecting must not perturb what it observes."""
    for text in ("", CHINESE, "too short", BAND_TEXT):
        bare = H.humanness(text, tier="lite")
        with_caveats, _ = H.humanness_with_caveats(text, tier="lite")
        assert bare == with_caveats, f"collection changed the score on {text[:30]!r}"


def test_the_logged_text_and_the_returned_text_are_the_same_string(caplog):
    """Two channels stating the same caveat differently is how one of them goes stale."""
    with caplog.at_level(logging.WARNING):
        _, caveats = H.humanness_with_caveats(BAND_TEXT, tier="lite")

    logged = {r.getMessage() for r in caplog.records}
    for caveat in caveats:
        assert caveat in logged, f"returned a caveat that was never logged: {caveat[:60]!r}"
