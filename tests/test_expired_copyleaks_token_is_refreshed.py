"""An expired Copyleaks token must be refreshed, not reused.

commercial.py:233: `if _CL_TOKEN["token"] and time.time() < _CL_TOKEN["exp"]:
return _CL_TOKEN["token"]` — the cached-token fast path requires BOTH a token
and an unexpired timestamp. The mutation and -> or returns the cached token
whenever it exists, even long after expiry — a 48h token used past its life
401s on every scan. Pinned with a _post_json spy: the expired case must re-auth.
"""
import os
import time
from unittest.mock import patch

import untell.detectors.commercial as commercial


def test_expired_token_is_refreshed():
    # Set inside the test (not at module import): the suite's autouse commercial-key
    # isolation clears ambient keys per test, and module-level env would be wiped.
    os.environ["COPYLEAKS_EMAIL"] = "e"
    os.environ["COPYLEAKS_API_KEY"] = "k"
    commercial._CL_TOKEN["token"] = "stale-token"
    commercial._CL_TOKEN["exp"] = time.time() - 100
    called = []

    def spy_post(*args, **kwargs):
        called.append(args)
        return {"access_token": "fresh"}

    try:
        with patch.object(commercial, "_post_json", side_effect=spy_post):
            assert commercial._copyleaks_token() == "fresh"
        assert len(called) == 1, "expired token must trigger a re-auth"
    finally:
        commercial._CL_TOKEN["token"] = None
        commercial._CL_TOKEN["exp"] = 0.0
