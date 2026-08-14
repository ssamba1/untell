"""verify()'s reported ai values are rounded to 4dp in the result dict.

verify.py:123 (aggregate max row) and :144 (commercial row) round the reported
ai to 4dp. The mutation 4 -> 5 changes the returned value: max = 0.123456
reports 0.1235 at 4dp but 0.12346 at 5dp. verify()'s result rows are the
published contract callers read.
"""
from unittest.mock import patch

from untell.scripts.verify import verify

FAKE = {
    "tier": "lite",
    "verdict_threshold": 0.45,
    "scored": True,
    "detectors": {"x": 0.123456},
    "max": 0.123456,
    "mean": 0.1,
}


def test_aggregate_max_ai_rounded_to_four_decimals():
    with patch("untell.scripts.verify.score_text", return_value=FAKE):
        r = verify("x", tier="lite")
    row = r["results"]["local:max (lite)"]
    assert row["ai"] == 0.1235, f"max ai not 4dp: {row['ai']!r}"


class _Exact:
    name = "rounding_commercial"
    tier = "commercial"

    def available(self) -> bool:
        return True

    def score(self, text: str) -> float:
        return 0.123456


def test_commercial_ai_rounded_to_four_decimals(monkeypatch):
    monkeypatch.setattr(
        "untell.detectors.commercial.commercial_detectors", lambda: [_Exact()]
    )
    r = verify("x", tier=None, threshold=0.30)
    row = r["results"]["rounding_commercial"]
    assert row["ai"] == 0.1235, f"commercial ai not 4dp: {row['ai']!r}"
