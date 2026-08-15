"""CV exactly at the erratic boundary (1.0) is not erratic.

humanness.py:372: `elif cv > 1.0:` — the erratic-burstiness penalty fires only
STRICTLY above 1.0. The mutation > -> >= applies it at exactly 1.0, dropping a
score of 100.0 to 97.0 for a text whose burstiness sits on the boundary (not
above it). Pinned with patched score_tells/score_text so the burstiness branch
is the only moving part.
"""
from unittest.mock import patch

from untell.humanness import humanness

TEXT = "the quick brown fox jumps over the lazy dog"


def _score(cv):
    tells = {"tells_per_100w": 0.0, "burstiness_cv": cv}
    det = {
        "tier": "lite",
        "max": 0.0,
        "mean": 0.0,
        "scored": True,
        "detectors": {"x": 0.0},
        "warning": None,
    }
    with patch("untell.humanness.score_tells", return_value=tells), patch(
        "untell.humanness.score_text", return_value=det
    ):
        return humanness(TEXT, tier="lite")


def test_cv_at_one_is_not_erratic():
    assert _score(1.0) == 100.0


def test_cv_above_one_is_erratic():
    assert _score(1.01) == 97.0
