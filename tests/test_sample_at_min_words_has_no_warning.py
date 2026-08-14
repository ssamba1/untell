"""A sample EXACTLY at MIN_SAMPLE_WORDS must not get the thin-sample warning.

voice.py:218: `if sample_words < MIN_SAMPLE_WORDS` — the warning fires only
BELOW 150 words. The mutation < -> <= fires it at exactly 150, producing a
self-contradictory warning ("sample is 150 words; below 150 the profile...").
The boundary is the point where the same-author signal becomes usable (per the
module docstring), so exactly-150 is a valid sample.
"""
from untell.scripts.voice import voice_report


def test_sample_at_min_words_has_no_warning():
    sample = " ".join(["word"] * 150)
    report = voice_report(sample, "a draft here.")
    assert "warning" not in report, report.get("warning")


def test_sample_below_min_words_warns():
    sample = " ".join(["word"] * 149)
    report = voice_report(sample, "a draft here.")
    assert "warning" in report
