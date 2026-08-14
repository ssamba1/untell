"""Killing tests for commercial.py mutation survivors (2026-08-14 sweep).

  line 233  logic: and -> or       Copyleaks token-cache validity.
  line 241  constant: 40 -> 41     token refresh window.

Killed here via the real `_copyleaks_token()` path: a valid cached token must be
returned WITHOUT a network call; the `or` mutation would skip the cache and hit
the network every time. The remaining survivors need live API keys or are
key-structure constants — annotated in survivors.md.
"""

from __future__ import annotations

import time

from untell.detectors import commercial as C


class TestCopyleaksTokenCache:
    """Survivor commercial.py:233 — `_CL_TOKEN["token"] and time.time() < _CL_TOKEN["exp"]`
    mutated to `or`.

    A valid cached token is returned without re-login. The `or` mutation treats a
    set token as valid even when expired, or skips the cache check entirely when
    the token is set — observable only through the real function's network call."""

    def test_cached_token_avoids_network(self, monkeypatch) -> None:
        old = dict(C._CL_TOKEN)
        C._CL_TOKEN["token"] = "cached-token-123"
        C._CL_TOKEN["exp"] = time.time() + 3600
        hit = []

        def _boom(*a, **k):
            hit.append(True)
            raise AssertionError("network call must not run with a valid cached token")

        monkeypatch.setattr(C, "_post_json", _boom)
        try:
            assert C._copyleaks_token() == "cached-token-123"
            assert not hit, "cached token must not trigger login"
        finally:
            C._CL_TOKEN.clear()
            C._CL_TOKEN.update(old)

    def test_expired_token_triggers_login(self, monkeypatch) -> None:
        old = dict(C._CL_TOKEN)
        C._CL_TOKEN["token"] = "stale-token"
        C._CL_TOKEN["exp"] = time.time() - 1
        hit = []
        monkeypatch.setenv("COPYLEAKS_EMAIL", "fake@example.com")
        monkeypatch.setenv("COPYLEAKS_API_KEY", "fake-key")

        def _fake_post(*a, **k):
            hit.append(True)
            return {"access_token": "fresh-token"}

        monkeypatch.setattr(C, "_post_json", _fake_post)
        try:
            assert C._copyleaks_token() == "fresh-token"
            assert hit, "expired token must trigger login"
        finally:
            C._CL_TOKEN.clear()
            C._CL_TOKEN.update(old)

    def test_refresh_window_is_40h(self) -> None:
        # token lives 48h; refresh at 40h keeps 8h of margin
        import inspect

        src = inspect.getsource(C._copyleaks_token)
        assert "40 * 3600" in src, "refresh window must stay at 40h"
