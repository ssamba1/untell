"""A detector that raises must not read as a pass.

verify.py line 152: when `d.score(text)` raises, the row is
{"ai": None, "passes": False, "error": ...}. The mutation False -> True would
make a broken detector report "passes": True — the worst possible direction
for a verdict surface. This test forces the exception path and pins the flag.
"""
from untell.scripts.verify import verify


class _Boom:
    name = "boom"
    tier = "lite"

    def available(self) -> bool:
        return True

    def score(self, text: str) -> float:
        raise RuntimeError("checker exploded")


def test_a_raising_detector_is_not_a_pass(monkeypatch):
    monkeypatch.setattr(
        "untell.detectors.commercial.commercial_detectors", lambda: [_Boom()]
    )
    result = verify("Some text to score.", tier="lite", threshold=0.3)
    row = result["results"]["boom"]
    assert row["ai"] is None
    assert row["passes"] is False, f"broken detector read as a pass: {row}"
    assert "checker exploded" in row["error"]
