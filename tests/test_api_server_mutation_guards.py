"""Killing tests for the api_server.py mutation survivors (2026-08-14 sweep).

  line 1025 logic: == -> !=        empty UNTELL_PORT check.

Killed here. 496 (rate-limit credential `or` -> `and`) is unkillable via the test
client: the mutation's "" credential falls back to the client IP, and TestClient
reuses one IP, so both paths trip identically (verified by applying the mutant —
req1=200/req2=429 in both cases). 409 (window constant), 428 (bucket-cap
boundary), and 650/682/715 (OpenAPI additionalProperties) are timing-dependent or
schema-description-only. All recorded as unkillable in survivors.md.
"""

from __future__ import annotations

from untell import api_server as A


class TestPortFromEnv:
    """Survivor api_server.py:1025 — `raw.strip() == ""` mutated to `!=`.

    An empty UNTELL_PORT falls back to the default. The mutation would send the
    empty string to int(), hitting the ValueError branch and exiting 2."""

    def test_empty_port_uses_default(self, monkeypatch) -> None:
        monkeypatch.setenv("UNTELL_PORT", "")
        assert A._port_from_env() == A._DEFAULT_PORT

    def test_unset_port_uses_default(self, monkeypatch) -> None:
        monkeypatch.delenv("UNTELL_PORT", raising=False)
        assert A._port_from_env() == A._DEFAULT_PORT

    def test_valid_port_is_parsed(self, monkeypatch) -> None:
        monkeypatch.setenv("UNTELL_PORT", "8123")
        assert A._port_from_env() == 8123


class TestHostFromEnv:
    """Survivor api_server.py:1090 — `os.environ.get("UNTELL_HOST", "0.0.0.0")`.

    The README's env-var table, api_server.py's own CORS comment and the CORS tests all document
    `untell-server` as binding 127.0.0.1 by default; the code bound 0.0.0.0, putting a server that
    ships an optional-auth path on the LAN under the documented quick start. Uvicorn's default is
    127.0.0.1 too. The default must stay localhost, and the env override must keep working.
    """

    def test_default_host_is_localhost(self, monkeypatch) -> None:
        monkeypatch.delenv("UNTELL_HOST", raising=False)
        assert A._host_from_env() == "127.0.0.1"

    def test_empty_host_falls_back_to_localhost(self, monkeypatch) -> None:
        monkeypatch.setenv("UNTELL_HOST", "  ")
        assert A._host_from_env() == "127.0.0.1"

    def test_env_override_wins(self, monkeypatch) -> None:
        monkeypatch.setenv("UNTELL_HOST", "0.0.0.0")
        assert A._host_from_env() == "0.0.0.0"
