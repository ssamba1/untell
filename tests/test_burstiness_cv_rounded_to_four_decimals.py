"""The burstiness CV is rounded to 4dp in the RETURNED value, not display.

tells.py:945: `return round((var**0.5) / mean, 4)`. The mutation 4 -> 5 changes
the returned coefficient — sentence lengths (5, 5, 10) give CV 0.353553...
which rounds to 0.3536 at 4dp but 0.35355 at 5dp. The CV is a published
detector signal, so its exact value is part of the API.
"""
from untell.scripts.tells import _burstiness_cv


def test_cv_is_rounded_to_four_decimals():
    cv = _burstiness_cv("hello. there. everyone here.")
    assert cv == 0.3536, f"CV not 4dp: {cv!r}"


def test_cv_undefined_for_single_sentence():
    assert _burstiness_cv("just one sentence here.") is None
