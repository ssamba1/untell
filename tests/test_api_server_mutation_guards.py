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


class TestMainStartsTheServer:
    """Killer for the 694f786 extraction botch: `def _host_from_env()` was dedented INSIDE
    ``main()``, so main() ended at the parser construction and returned None — ``untell-server``
    printed nothing and exited 0, and the startup code (add_argument/parse_args/uvicorn.run)
    sat unreachable after _host_from_env's ``return``. Verified at HEAD: `python -m
    untell.api_server --help` produced zero output. The Dockerfile entrypoint and the CI docker
    job both depend on main() actually launching uvicorn."""

    def test_main_launches_uvicorn_with_parsed_args(self, monkeypatch) -> None:
        calls: list[tuple] = []
        monkeypatch.setattr("uvicorn.run", lambda *a, **k: calls.append((a, k)))
        rc = A.main(["--host", "127.0.0.1", "--port", "8123"])
        assert rc == 0
        assert len(calls) == 1, f"uvicorn.run called {len(calls)} times, not once"
        (app,), kwargs = calls[0]
        assert app == "untell.api_server:app"
        assert kwargs["host"] == "127.0.0.1"
        assert kwargs["port"] == 8123
        assert kwargs["reload"] is False

    def test_main_default_host_is_localhost(self, monkeypatch) -> None:
        monkeypatch.delenv("UNTELL_HOST", raising=False)
        calls: list[tuple] = []
        monkeypatch.setattr("uvicorn.run", lambda *a, **k: calls.append((a, k)))
        A.main([])
        (_,), kwargs = calls[0]
        assert kwargs["host"] == "127.0.0.1"

    def test_main_help_prints_usage(self) -> None:
        import subprocess
        import sys
        from pathlib import Path

        result = subprocess.run(
            [sys.executable, "-m", "untell.api_server", "--help"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
            cwd=Path(__file__).resolve().parent.parent,
        )
        assert result.returncode == 0
        assert "usage: untell-server" in (result.stdout + result.stderr)
