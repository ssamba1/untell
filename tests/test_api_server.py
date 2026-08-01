"""Tests for the REST API server — offline, no network."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# The REST API is an optional extra (pip install .[server]). Skip the whole
# module when FastAPI is absent rather than crashing collection.
pytest.importorskip("fastapi")

import untell.api_server as _  # noqa: E402,F401  — side-effect import for patch resolution


def test_health_endpoint():
    """The health endpoint returns status ok and detector info."""
    with patch("untell.api_server.load_env"):
        from untell.api_server import app

        client = MagicMock()

        # FastAPI test client
        from fastapi.testclient import TestClient

        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "detector_tier" in data


def test_score_endpoint():
    """The score endpoint accepts text and returns detector scores."""
    with patch("untell.api_server.load_env"):
        from fastapi.testclient import TestClient

        from untell.api_server import app

        client = TestClient(app)
        resp = client.post("/score", json={"text": "This is a test.", "tier": "lite"})
        assert resp.status_code == 200
        data = resp.json()
        assert "max" in data
        assert "detectors" in data
        assert "tier" in data


def test_tells_endpoint():
    """The tells endpoint returns AI tell counts."""
    with patch("untell.api_server.load_env"):
        from fastapi.testclient import TestClient

        from untell.api_server import app

        client = TestClient(app)
        resp = client.post("/tells", json={"text": "Furthermore, we leverage robust solutions."})
        assert resp.status_code == 200
        data = resp.json()
        assert "tells" in data
        assert "tells_per_100w" in data
        assert data["tells"] > 0


def test_auth_blocks_unauthorized():
    """When UNTELL_API_KEY is set, requests without a key get 401."""
    with patch("untell.api_server._API_KEY", "secret123"):
        with patch("untell.api_server.load_env"):
            from fastapi.testclient import TestClient

            from untell.api_server import app

            client = TestClient(app)
            resp = client.post("/score", json={"text": "test", "tier": "lite"})
            assert resp.status_code == 401


def test_auth_allows_with_valid_key():
    """When UNTELL_API_KEY is set, requests with the correct key pass."""
    with patch("untell.api_server._API_KEY", "secret123"):
        with patch("untell.api_server.load_env"):
            from fastapi.testclient import TestClient

            from untell.api_server import app

            client = TestClient(app)
            resp = client.post("/score", json={"text": "test", "tier": "lite"}, headers={"X-API-Key": "secret123"})
            assert resp.status_code == 200


def test_empty_text_returns_422():
    """Missing or empty text should return 422."""
    with patch("untell.api_server.load_env"):
        from fastapi.testclient import TestClient

        from untell.api_server import app

        client = TestClient(app)
        # Missing text field entirely
        resp = client.post("/score", json={"tier": "lite"})
        assert resp.status_code == 422


def test_sentences_endpoint():
    """The sentences endpoint returns per-sentence scores."""
    with patch("untell.api_server.load_env"):
        from fastapi.testclient import TestClient

        from untell.api_server import app

        client = TestClient(app)
        resp = client.post("/sentences", json={"text": "First sentence here. Second one here.", "tier": "lite"})
        assert resp.status_code == 200
        data = resp.json()
        assert "sentences" in data
        assert len(data["sentences"]) > 0


def test_verify_endpoint():
    """The verify endpoint returns a verdict dict."""
    with patch("untell.api_server.load_env"):
        from fastapi.testclient import TestClient

        from untell.api_server import app

        client = TestClient(app)
        resp = client.post("/verify", json={"text": "Test text here for verification checks today."})
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data


def test_humanize_endpoint():
    """The humanize endpoint runs the closed loop and returns final text."""
    with patch("untell.api_server.load_env"):
        with patch("untell.api_server.untell_text") as mock_untell:
            mock_untell.return_value = {
                "final": "Humanized text.",
                "pre": {"max": 0.8},
                "post": {"max": 0.2},
                "iterations": 2,
                "stopped": "passed",
            }
            from fastapi.testclient import TestClient

            from untell.api_server import app

            client = TestClient(app)
            resp = client.post("/humanize", json={"text": "AI generated text here.", "tier": "lite"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["final"] == "Humanized text."
            assert "pre" in data
            assert "post" in data
            assert "iterations" in data


def test_ceiling_endpoint():
    """The ceiling endpoint measures free evasion.

    Patched at ``eval.ceiling.measure_ceiling``, NOT ``untell.api_server.measure_ceiling``: the
    endpoint imports it lazily inside the function body (deliberately — a module-level import would
    pull the eval harness in on every server start), so there is no attribute of that name on
    ``untell.api_server`` to patch and the test raised AttributeError before reaching the request.
    It went unnoticed because the whole module skips when FastAPI is absent, which it was.
    """
    with patch("untell.api_server.load_env"):
        with patch("eval.ceiling.measure_ceiling") as mock_ceiling:
            mock_ceiling.return_value = {"samples": [], "mean_by_strategy": {}, "bypass_rates": {}}
            from fastapi.testclient import TestClient

            from untell.api_server import app

            client = TestClient(app)
            resp = client.post("/ceiling", json={"n": 3, "tier": "lite"})
            assert resp.status_code == 200
            data = resp.json()
            assert "samples" in data
            assert "mean_by_strategy" in data


def test_humanize_with_composite_rewriter():
    """The humanize endpoint supports --rewriter composite."""
    with patch("untell.api_server.load_env"):
        with patch("untell.api_server.untell_text") as mock_untell:
            mock_untell.return_value = {
                "final": "Better text.",
                "pre": {"max": 0.7},
                "post": {"max": 0.3},
                "iterations": 3,
                "stopped": "passed",
            }
            from fastapi.testclient import TestClient

            from untell.api_server import app

            client = TestClient(app)
            resp = client.post(
                "/humanize",
                json={"text": "AI text.", "tier": "lite", "rewriter": "composite"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["final"] == "Better text."
