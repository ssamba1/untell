"""Tests for the REST API server — offline, no network."""
from __future__ import annotations

import os
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


def test_auth_blocks_unauthorized(monkeypatch):
    """When UNTELL_API_KEY is set, requests without a key get 401."""
    monkeypatch.setenv("UNTELL_API_KEY", "secret123")
    with patch("untell.api_server.load_env"):
        from fastapi.testclient import TestClient

        from untell.api_server import app

        client = TestClient(app)
        resp = client.post("/score", json={"text": "test", "tier": "lite"})
        assert resp.status_code == 401


def test_auth_allows_with_valid_key(monkeypatch):
    """When UNTELL_API_KEY is set, requests with the correct key pass."""
    monkeypatch.setenv("UNTELL_API_KEY", "secret123")
    with patch("untell.api_server.load_env"):
        from fastapi.testclient import TestClient

        from untell.api_server import app

        client = TestClient(app)
        resp = client.post("/score", json={"text": "test", "tier": "lite"}, headers={"X-API-Key": "secret123"})
        assert resp.status_code == 200


def test_auth_honours_a_key_set_only_in_dotenv(tmp_path, monkeypatch):
    """A key in .env must protect the server, not leave it wide open.

    The real startup order is import-then-lifespan: uvicorn imports the module, and only then
    does ``lifespan`` call ``load_env()``. Reading the key at import meant a .env-only key was
    always empty at check time, so every protected endpoint served unauthenticated requests.
    ``load_env`` is deliberately *not* patched here — this exercises the whole path.
    """
    (tmp_path / ".env").write_text("UNTELL_API_KEY=from-dotenv\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    from fastapi.testclient import TestClient

    from untell.api_server import app

    # patch.dict, not monkeypatch.delenv: load_env *adds* the key to os.environ during the test,
    # and monkeypatch only restores vars it was told about. patch.dict snapshots the whole mapping.
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("UNTELL_API_KEY", None)
        with TestClient(app) as client:  # `with` runs the lifespan hook
            assert client.post("/score", json={"text": "test", "tier": "lite"}).status_code == 401
            assert client.post(
                "/score", json={"text": "test", "tier": "lite"}, headers={"X-API-Key": "wrong"}
            ).status_code == 401
            assert client.post(
                "/score", json={"text": "test", "tier": "lite"}, headers={"X-API-Key": "from-dotenv"}
            ).status_code == 200


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


def test_scoring_and_gates_are_thread_safe():
    """The REST API serves concurrent requests, and every scorer here caches state in module
    globals — detector instances, the tells registry, the quality metric backend.

    None of that is lock-protected, so a future change that makes one of those caches mutable
    mid-flight would corrupt results only under load, which is exactly the failure a single-threaded
    test suite never sees. MEASURED: 96 calls across 12 threads, 0 errors, and each input produced
    one stable answer. (The ML paths were checked the same way separately — 40 concurrent NLI +
    spaCy calls with cold caches produced 4 distinct verdicts, 10 each, no races.)
    """
    import concurrent.futures as cf

    from untell.scripts.hedges import certainty_kept
    from untell.scripts.numerals import numbers_kept
    from untell.scripts.quality import similarity
    from untell.scripts.score import score_text
    from untell.scripts.tells import score_tells

    texts = [
        "Furthermore, organizations leverage these technologies to optimize efficiency.",
        "Some studies suggest that 7 of the 19 programs may improve outcomes.",
        "I went to the store and forgot the milk again, third time this month.",
        "Revenue fell slightly last quarter while costs rose modestly across regions.",
    ]

    def work(i: int):
        t, u = texts[i % len(texts)], texts[(i + 1) % len(texts)]
        return (
            score_text(t, tier="lite")["max"],
            score_tells(t)["tells"],
            round(similarity(t, u), 4),
            numbers_kept(t, u),
            certainty_kept(t, u),
        )

    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        results = [f.result() for f in cf.as_completed([ex.submit(work, i) for i in range(48)])]

    assert len(results) == 48
    # Same input must give the same answer no matter how the threads interleaved.
    single_threaded = {work(i) for i in range(len(texts))}
    assert set(results) == single_threaded, "concurrent results diverged from serial ones"


def test_oversized_text_is_rejected_at_the_edge():
    """One unbounded request could occupy a worker for a minute.

    `preserve.lock()` runs BEFORE scoring and was uncapped. MEASURED, after the spaCy model warms,
    it scales ~45ms per KB: 188 KB takes 8.5s, so roughly a megabyte ties up a worker for ~45s.
    score.py's 50k cap did not protect that path, because it applies after locking.

    The bound is score.py's own constant, so the network edge and the scorer cannot drift apart.
    """
    from fastapi.testclient import TestClient

    from untell.api_server import app
    from untell.scripts.score import MAX_INPUT_CHARS

    client = TestClient(app)
    oversized = "x " * (MAX_INPUT_CHARS // 2 + 500)
    assert len(oversized) > MAX_INPUT_CHARS

    for path in ("/score", "/tells", "/sentences", "/humanize", "/verify"):
        r = client.post(path, json={"text": oversized, "tier": "lite"})
        assert r.status_code == 422, f"{path} accepted {len(oversized)} chars: {r.status_code}"

    # ...and ordinary requests still work — the bound must not be so tight it breaks real use.
    ok = "Furthermore, organizations leverage these technologies to optimize efficiency."
    assert client.post("/score", json={"text": ok, "tier": "lite"}).status_code == 200
    assert client.post("/tells", json={"text": ok}).status_code == 200


class TestAuthSurface:
    """The existing auth tests cover blocked / allowed / .env. These cover the ways auth is
    usually bypassed rather than defeated: an alternate scheme, and path variants that miss an
    exemption list.

    Worth pinning because this file already shipped one auth bug — the key was read into a
    module-level constant, so a key set after import left every check on the "no key configured =
    open access" branch.
    """

    TEXT = "Furthermore, organizations leverage these technologies to optimize efficiency."
    KEY = "s3cret-test-key"

    def _client(self, monkeypatch):
        from fastapi.testclient import TestClient

        from untell.api_server import app

        monkeypatch.setenv("UNTELL_API_KEY", self.KEY)
        return TestClient(app)

    @pytest.mark.parametrize(
        ("headers", "expected"),
        [
            ({}, 401),
            ({"X-API-Key": "wrong"}, 401),
            ({"X-API-Key": KEY}, 200),
            ({"x-api-key": KEY}, 200),
            ({"Authorization": f"Bearer {KEY}"}, 200),
            ({"Authorization": "Bearer wrong"}, 401),
            ({"Authorization": KEY}, 401),
        ],
        ids=["none", "wrong", "header", "lowercase-header", "bearer", "bearer-wrong", "bare-token"],
    )
    def test_key_is_required_and_verified(self, monkeypatch, headers, expected):
        r = self._client(monkeypatch).post(
            "/score", json={"text": self.TEXT, "tier": "lite"}, headers=headers
        )
        assert r.status_code == expected

    @pytest.mark.parametrize("path", ["/score/", "/SCORE", "/health/../score", "//score"])
    def test_path_variants_do_not_slip_past_the_exemption_list(self, monkeypatch, path):
        """The middleware exempts /health, /docs, /openapi.json and /redoc by exact match. A
        variant that routes to a real endpoint while missing that comparison would be an open
        door."""
        r = self._client(monkeypatch).post(path, json={"text": self.TEXT, "tier": "lite"})
        assert r.status_code == 401, f"{path} reached the app without a key ({r.status_code})"

    @pytest.mark.parametrize("path", ["/health", "/docs", "/openapi.json"])
    def test_exempt_paths_stay_reachable_without_a_key(self, monkeypatch, path):
        """Locking these would break health checks and the documented /docs UI."""
        assert self._client(monkeypatch).get(path).status_code == 200

    def test_no_key_configured_means_open_access(self, monkeypatch):
        """Documented default. Asserted so it stays a deliberate choice rather than an accident."""
        from fastapi.testclient import TestClient

        from untell.api_server import app

        monkeypatch.delenv("UNTELL_API_KEY", raising=False)
        r = TestClient(app).post("/score", json={"text": self.TEXT, "tier": "lite"})
        assert r.status_code == 200
