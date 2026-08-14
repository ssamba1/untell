"""A detector value exactly at the verdict cut must not pass.

verify.py:106: `"passes": val < verdict_cut` — a detector scoring EXACTLY at the
published cut (0.45 on the stdlib lite path) must fail. The mutation < -> <=
flips it to pass. The cut is a published constant, so the exact-equality case
is reachable — the 'measure-zero with real floats' claim was wrong; the stdlib
path publishes an exact cut and a detector value can land on it.
"""
from unittest.mock import patch

from untell.scripts.verify import verify

FAKE = {
    "tier": "lite",
    "verdict_threshold": 0.45,
    "scored": True,
    "detectors": {"perplexity_burstiness": 0.45},
    "max": 0.45,
    "mean": 0.45,
}


def test_detector_at_exact_cut_does_not_pass():
    with patch("untell.scripts.verify.score_text", return_value=FAKE):
        r = verify("x", tier="lite")
    row = r["results"]["local:perplexity_burstiness"]
    assert row["ai"] == 0.45
    assert row["verdict_threshold"] == 0.45
    assert row["passes"] is False, f"detector at exact cut read as pass: {row}"


def test_detector_below_cut_passes():
    below = dict(FAKE)
    below["detectors"] = {"perplexity_burstiness": 0.44}
    below["max"] = 0.44
    with patch("untell.scripts.verify.score_text", return_value=below):
        r = verify("x", tier="lite")
    assert r["results"]["local:perplexity_burstiness"]["passes"] is True


class _Exact:
    """Commercial detector returning EXACTLY the caller's threshold."""

    name = "exact_commercial"
    tier = "commercial"

    def available(self) -> bool:
        return True

    def score(self, text: str) -> float:
        return 0.30  # == threshold passed below


def test_commercial_detector_at_exact_threshold_does_not_pass(monkeypatch):
    monkeypatch.setattr(
        "untell.detectors.commercial.commercial_detectors", lambda: [_Exact()]
    )
    r = verify("x", tier=None, threshold=0.30)
    row = r["results"]["exact_commercial"]
    assert row["ai"] == 0.30
    assert row["passes"] is False, f"commercial detector at exact threshold passed: {row}"
