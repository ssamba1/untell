"""Tell density feeds the single-sentence signal, not a collapsed zero.

perplexity_burstiness.py:202: `float(score_tells(text).get("tells_per_100w")
or 0.0)` — the tells-per-100w density is the signal. The mutation or -> and
makes the expression `density and 0.0` which is ALWAYS 0.0 when density is
present: every tell density collapses, the tell_signal term vanishes, and
only the fallback remains (1.0 -> 0.2 for density 40). Pinned via the patched
score_tells.
"""
from unittest.mock import patch

from untell.detectors.perplexity_burstiness import _single_sentence_signal


def test_tell_density_feeds_signal():
    with patch(
        "untell.scripts.tells.score_tells", return_value={"tells_per_100w": 40.0}
    ):
        assert _single_sentence_signal("some text", fallback=0.2) == 1.0
