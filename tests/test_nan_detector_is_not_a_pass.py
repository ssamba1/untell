"""A NaN-returning detector must not read as a pass.

verify.py:139: a detector whose score is NaN reports {"ai": None, "passes":
False, "error": "detector returned NaN"} — the comment says a broken detector
must not read as a score. The mutation False -> True makes NaN report
passes=True (the caller would treat un-scored text as clean).
"""

from untell.scripts.verify import verify


class _NaN:
    name = "nan_detector"
    tier = "commercial"

    def available(self) -> bool:
        return True

    def score(self, text: str) -> float:
        return float("nan")


def test_nan_detector_is_not_a_pass(monkeypatch):
    monkeypatch.setattr(
        "untell.detectors.commercial.commercial_detectors", lambda: [_NaN()]
    )
    r = verify("x", tier=None, threshold=0.30)
    row = r["results"]["nan_detector"]
    assert row["ai"] is None
    assert row["passes"] is False, f"NaN detector read as pass: {row}"
    assert "NaN" in row["error"]
