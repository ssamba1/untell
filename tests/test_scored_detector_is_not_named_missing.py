"""A detector that DID score must not be named as missing from the roster.

score.py:1129: `d.name not in scores` — the short-roster caveat names detectors
the requested tier expects that did not turn up. The mutation not-in -> in
inverts membership: a detector whose score IS in the results gets named as
"ran without <detector>", the exact opposite of the truth. Forced with a fake
detector that is tier-qualified, in scores, not opt-in, and unavailable.
"""
from unittest.mock import patch

from untell.scripts.score import _short_roster_note


class _Missing:
    name = "fake_det"
    tier = "full"

    def available(self) -> bool:
        return False


def _note(scores: dict):
    with patch("untell.detectors.base.all_detectors", return_value=[_Missing()]):
        with patch("untell.detectors.base._tier_at_most", return_value=True):
            return _short_roster_note("full", "full", scores)


def test_scored_detector_is_not_named_as_missing():
    out = _note({"fake_det": 0.5})
    assert out is None, f"a detector in scores was named missing: {out}"


def test_unscored_unavailable_detector_is_named():
    out = _note({})
    assert out is not None
    assert "fake_det" in out
