"""Per-detector 4dp rounding must not collapse a tiny-but-real signal.

score.py:744: `scores[d.name] = round(clamped, 4)` — a detector returning
0.000045 reports 0.0 (collapsed), and with all other detectors at 0.0 the
aggregate max is 0.0. The mutation 4 -> 5 keeps 5e-05, whose 4dp re-round is
0.0001 — the max flips from 0.0 to 0.0001. Prior '4dp dominates, 5dp
invisible' UNKILLABLE note wrong: the collapse is exactly the observable.
"""
from unittest.mock import patch

from untell.scripts.score import score_text


class _Tiny:
    name = "tiny"
    tier = "lite"

    def score(self, text: str) -> float:
        return 0.000045


class _Zero:
    name = "zero"
    tier = "lite"

    def score(self, text: str) -> float:
        return 0.0


def test_tiny_signal_not_collapsed_to_zero():
    with patch(
        "untell.scripts.score.load_detectors", return_value=[_Tiny(), _Zero()]
    ):
        r = score_text("hello world text here", tier="lite")
    # The 4dp per-detector rounding collapses 0.000045 to 0.0; a 5dp rounding
    # would keep 5e-05 and the aggregate max would read 0.0001.
    assert r["detectors"]["tiny"] == 0.0
    assert r["max"] == 0.0
