"""Per-100w rates use the 100 multiplier in the RETURNED profile.

voice.py:157/160: comma_per_100w and first_person_per_100w are
`round(count / n_words * 100, 4)`. The mutation 100 -> 101 changes the returned
profile (2 commas / 7 words = 28.5714 at 100, 28.8571 at 101). style_profile
is a published per-feature dict — exact values are the API.
"""
from untell.scripts.voice import style_profile


def test_comma_rate_uses_per_100w():
    profile = style_profile("Hello, world. This is a test, really.")
    assert profile["comma_per_100w"] == 28.5714, profile["comma_per_100w"]


def test_first_person_rate_uses_per_100w():
    profile = style_profile("I went to the shop and I bought some milk.")
    assert profile["first_person_per_100w"] == 20.0, profile["first_person_per_100w"]
