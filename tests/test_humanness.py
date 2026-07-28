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
