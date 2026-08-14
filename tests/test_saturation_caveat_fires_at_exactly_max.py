"""The saturation caveat fires AT the saturated max, not only above it.

run.py:196: `if a < _SATURATED_MAX or b < _SATURATED_MAX: return None` — the
caveat is suppressed only when some score is BELOW 0.99. The mutation < -> <=
suppresses it when a score is EXACTLY 0.99, silently dropping the honest
"the hardest detector is pinned" warning at the boundary where it matters
most. Pure function — no rewrite cycle needed.
"""
from untell.scripts.run import _saturated_max_caveat


def test_caveat_fires_at_exactly_saturated_max():
    out = _saturated_max_caveat(
        {"max": 0.99, "mean": 0.9}, {"max": 0.99, "mean": 0.8}
    )
    assert out is not None
    assert "pinned" in out


def test_caveat_suppressed_below_saturated_max():
    out = _saturated_max_caveat(
        {"max": 0.5, "mean": 0.4}, {"max": 0.5, "mean": 0.4}
    )
    assert out is None
