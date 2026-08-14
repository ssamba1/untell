"""style_profile's burst coefficient is rounded to 4dp in the returned value.

voice.py:156: `"burst": round(st.pstdev(lengths) / mean_len, 4)`. The mutation
4 -> 5 changes the returned profile: sentence word-counts (1,1,1,2) give burst
0.346410... which rounds to 0.3464 at 4dp but 0.34641 at 5dp. style_profile is
a published per-feature dict, so its exact values are part of the API.
"""
from untell.scripts.voice import style_profile


def test_burst_rounded_to_four_decimals():
    profile = style_profile("Hello. World. Done. Two words.")
    assert profile["burst"] == 0.3464, f"burst not 4dp: {profile['burst']!r}"
