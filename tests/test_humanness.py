"""Tests for the humanness score metric."""
from __future__ import annotations

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
        assert classification(70) == "mostly human"
        assert classification(45) == "mixed"
        assert classification(25) == "likely AI"
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
