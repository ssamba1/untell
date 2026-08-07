"""Tests for the humanness score metric."""
from __future__ import annotations

import json

import pytest

from untell.humanness import classification, humanness


class TestHumanness:
    def test_ai_text_scores_low(self):
        text = "Furthermore, we leverage robust solutions to optimize efficiency across various sectors. Moreover, the results demonstrate significant improvements."
        score = humanness(text, tier="lite")
        # AI text should score in the lower range
        assert score < 70, f"Expected AI text to score low, got {score}"

    def test_human_text_scores_higher(self):
        text = "i grabbed coffee on the way in and the line was way too long for a tuesday. spilled half of it getting out the door, classic. some mornings just go like that and you roll with it."
        score = humanness(text, tier="lite")
        # Human text should score higher than clearly AI text
        assert score > 30, f"Expected human text to score >30, got {score}"

    def test_empty_text_neutral(self):
        assert humanness("", tier="lite") == 50.0
        assert humanness("   ", tier="lite") == 50.0

    def test_classification_thresholds(self):
        assert classification(85) == "human"
        assert classification(65) == "mostly human"
        assert classification(50) == "mixed"
        assert classification(35) == "likely AI"
        assert classification(10) == "AI"

    def test_regression_formulaic_is_lower(self):
        formulaic = "Moreover, the data demonstrates significant improvement. Furthermore, the results are robust."
        natural = "The data shows real improvement. The results are solid and hold up across different tests."
        formulaic_score = humanness(formulaic, tier="lite")
        natural_score = humanness(natural, tier="lite")
        assert formulaic_score < natural_score, (
            f"Expected formulaic ({formulaic_score}) < natural ({natural_score})"
        )


def test_tells_scorer_separates_human_from_ai_with_no_false_positives():
    """The tells scorer now drives selection tie-breaks in the loop, so its discrimination is
    load-bearing and must not silently regress.

    Measured, it is the STRONGEST discriminator in the system: perfect separation with zero false
    positives on human prose, better than any neural detector — and unlike them it does not
    anti-correlate with human-ness, which is exactly why it is the right tie-breaker.
    """
    from untell.scripts.tells import score_tells

    human = [
        "I went to the store yesterday and forgot my wallet again. Third time this month.",
        "My grandmother kept every letter my grandfather sent during the war, tied with brown string.",
        "The bus was late so I walked. Rain the whole way. My shoes are still wet by the radiator.",
        "He never did learn to swim properly, just sort of thrashed until he got where he was going.",
    ]
    ai = [
        "Furthermore, artificial intelligence has fundamentally transformed numerous industries.",
        "In today's rapidly evolving digital landscape, cybersecurity has become paramount.",
        "Moreover, organizations increasingly leverage these technologies to optimize efficiency.",
        "It is important to note that a comprehensive strategy is essential for sustainable success.",
    ]
    h = [score_tells(t)["tells_per_100w"] for t in human]
    a = [score_tells(t)["tells_per_100w"] for t in ai]

    assert max(h) == 0.0, f"false positives on human prose: {h}"
    assert min(a) > max(h), f"no separation: human {h} vs ai {a}"
    assert sum(a) / len(a) > 5.0, f"AI tell rate collapsed: {a}"


def test_dead_detectors_do_not_inflate_the_humanness_score(monkeypatch):
    """`.get("max", 0.5)` could never fire — score_text ALWAYS returns a "max" key, and when
    nothing scored that key is a 0.0 PLACEHOLDER. At weight 0.50 that reads as "no detector
    thinks this is AI" and lifted the score by fifty points, so a broken ML stack reported
    formulaic AI text as MORE human than a working one did:

        working ML stack   60.2
        dead ML stack      71.1   <- the failure looked like a better result

    score_text sets `scored: False` for exactly this case. The detector weight is now
    redistributed across the signals that did produce something.
    """
    import untell.humanness as h

    ai_text = (
        "Furthermore, we leverage robust solutions to optimize efficiency across various "
        "sectors. Moreover, the results demonstrate significant improvements across all "
        "measured dimensions."
    )
    working = h.humanness(ai_text, tier="lite")

    monkeypatch.setattr(h, "score_text", lambda text, tier="full", threshold=0.30: {
        "detectors": {}, "max": 0.0, "mean": 0.0, "ai_percent": 0.0,
        "threshold": threshold, "flagged": False, "scored": False,
        "warning": "no detector produced a score",
    })
    dead = h.humanness(ai_text, tier="lite")
    assert dead <= working, (
        f"a dead detector stack scored {dead} against {working} working — the placeholder is "
        f"being read as a human verdict"
    )


def test_documented_bands_match_the_implementation():
    """The docstring and the code must agree. They once did not: the docstring advertised
    80 / 50-80 / 30-50 / 30 while classification() implemented 80 / 55 / 35 / 15, so a score of 40
    was "likely AI" by the docs and "mixed" by the code.

    Boundaries recalibrated 2026-08-07 to 75 / 60 / 45 / 30 — measured, the classes are fully
    separable at the full tier (lowest human 75.6, highest AI 72.0 over 80 HC3+RAID pairs)."""
    from untell.humanness import classification

    assert classification(75) == "human"
    assert classification(74.9) == "mostly human"
    assert classification(60) == "mostly human"
    assert classification(59.9) == "mixed"
    assert classification(45) == "mixed"
    assert classification(44.9) == "likely AI"
    assert classification(30) == "likely AI"
    assert classification(29.9) == "AI"


def test_the_bands_actually_separate_the_classes():
    """The failure that forced the recalibration: on the full tier the old bands never produced
    an AI verdict about AI text — 0/60 on HC3 and 0/40 on RAID reached "likely AI", while the
    ranking was perfect (AUROC 1.0000 on RAID). The score was right; the labels were wrong.

    Pinned as boundaries rather than as a live corpus run so it stays fast and offline."""
    from untell.humanness import classification

    # Observed ranges over 80 HC3+RAID pairs at tier=full.
    assert classification(75.6) == "human", "the lowest observed human score must read as human"
    assert classification(72.0) != "human", "the highest observed AI score must not read as human"
    for ai_score in (41.6, 43.5, 47.8, 50.0):
        assert classification(ai_score) in ("mixed", "likely AI", "AI"), (
            f"typical AI score {ai_score} must not be labelled human-ish"
        )


class TestTooShortToScore:
    """A headline command that advertises "how human does it read" must not answer on one word.

    MEASURED before the guard, at full confidence:
        humanness("Hello")     -> 100.0  "human"
        humanness("It works.") -> 100.0  "human"

    None of the three signals means anything at that length. Burstiness needs two sentences, a
    single tell reads as 100 per 100 words, and the detector already abstains below its own
    `_MIN_WORDS_FOR_SIGNAL` — humanness was ignoring that abstention and scoring anyway.
    """

    @pytest.mark.parametrize(
        "text", ["Hello", "It works.", "Yes.", "one two three four"],
        ids=["one-word", "two-words", "single", "four-words"],
    )
    def test_short_text_is_undetermined_not_confident(self, text):
        from untell.humanness import classification, humanness

        score = humanness(text, tier="lite")
        assert score == 50.0, f"{text!r} scored {score}"
        assert classification(score) == "mixed"

    def test_the_boundary_is_scored(self):
        """At the threshold the signals become meaningful again, so the guard must not swallow it."""
        from untell.humanness import humanness

        assert humanness("The cat sat on mats", tier="lite") != 50.0

    def test_real_text_is_unaffected(self):
        from untell.humanness import classification, humanness

        ai = (
            "Furthermore, artificial intelligence has fundamentally transformed numerous industries. "
            "Moreover, organizations increasingly leverage these technologies to optimize efficiency. "
            "Overall, the transformative impact continues to expand across various sectors."
        )
        human = (
            "I almost missed the bus. Rain again — of course. My shoes were soaked through by the "
            "time the 8:14 finally rattled up, half-empty, smelling faintly of wet dog."
        )
        assert humanness(human, tier="lite") > humanness(ai, tier="lite")
        assert classification(humanness(human, tier="lite")) in ("human", "mostly human")


class TestTheScoreNamesItsTier:
    """The number is a fact about the text AND the tier; only one used to be on screen.

    MEASURED on 6 real HC3 AI texts: lite gives mean 62.8 and calls all six "mostly human",
    full gives mean 43.4 and calls all six "mixed". A 19.4-point swing and a different band,
    from a flag the output never mentioned. Same defect class as /ceiling not naming its corpus.
    """

    def test_json_reports_the_tier(self, capsys, monkeypatch):
        monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
        from untell.humanness import main

        assert main(["--tier", "lite", "--json", "The cat sat on the mat. It was warm there."]) == 0
        parsed = json.loads(capsys.readouterr().out)
        assert parsed["tier"] == "lite"
        assert {"score", "classification", "tier"} <= set(parsed)

    def test_text_output_reports_the_tier(self, capsys, monkeypatch):
        monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
        from untell.humanness import main

        main(["--tier", "lite", "The cat sat on the mat. It was warm there."])
        assert "tier=lite" in capsys.readouterr().out

    def test_the_reported_tier_is_the_one_requested(self, capsys, monkeypatch):
        """Guards against a hard-coded default being echoed back instead of the real tier."""
        monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
        from untell.humanness import main

        for tier in ("lite", "heavy"):
            main(["--tier", tier, "--json", "The cat sat on the mat. It was warm."])
            assert json.loads(capsys.readouterr().out)["tier"] == tier
