"""Whitespace text never reaches the commercial API.

commercial.py:98: `if not self.available() or not text.strip(): return None` —
whitespace-only input must short-circuit before any network call. The
mutation or -> and makes the guard require BOTH conditions to fail, so with
the detector available, whitespace text proceeds to the paid API (wasting a
call and charging the user for an empty scan). Pinned with a _post_json spy:
the original must never call it.
"""
import os
from unittest.mock import patch

import untell.detectors.commercial as commercial

os.environ["ORIGINALITY_API_KEY"] = "fake-key"


def test_whitespace_never_reaches_api():
    d = commercial.OriginalityDetector()
    called = []

    def spy_post(*args, **kwargs):
        called.append(args)
        return {"score": {"ai": 0.9}}

    with patch.object(d, "available", return_value=True), patch.object(
        commercial, "_post_json", side_effect=spy_post
    ):
        assert d.score("   ") is None
    assert called == [], "the API must not be called for whitespace input"
