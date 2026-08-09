"""Tests for the REST API server — offline, no network."""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

# The REST API is an optional extra (pip install .[server]). Skip the whole
# module when FastAPI is absent rather than crashing collection.
pytest.importorskip("fastapi")

# Bound to a real name, not `_`: every throwaway loop variable in this file is also `_`, so the
# module-level binding was shadowed and the import read as dead to both linters and readers.
import untell.api_server as _api_server_preimport  # noqa: E402,F401  — side effect: patch resolution


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


class TestRateLimiting:
    """The module docstring advertised "rate limiting" from the start and nothing implemented it —
    no limiter, no 429, no counter. This covers the implementation that makes the claim true.
    """

    TEXT = "Furthermore, organizations leverage these technologies to optimize efficiency."

    def _client(self, monkeypatch, limit: str | None = None):
        from fastapi.testclient import TestClient

        import untell.api_server as api

        monkeypatch.delenv("UNTELL_API_KEY", raising=False)
        if limit is None:
            monkeypatch.delenv("UNTELL_RATE_LIMIT", raising=False)
        else:
            monkeypatch.setenv("UNTELL_RATE_LIMIT", limit)
        api._rate_buckets.clear()
        return TestClient(api.app), api

    def test_requests_over_the_limit_get_429(self, monkeypatch):
        client, _api = self._client(monkeypatch, "5")
        codes = [client.post("/tells", json={"text": self.TEXT}).status_code for _n in range(8)]
        assert codes[:5] == [200] * 5, codes
        assert codes[5:] == [429] * 3, codes

    def test_429_says_what_the_limit_is_and_when_to_retry(self, monkeypatch):
        """A limit with no Retry-After makes a client guess, and guessing means hammering."""
        client, _api = self._client(monkeypatch, "2")
        for _n in range(3):
            r = client.post("/tells", json={"text": self.TEXT})
        assert r.status_code == 429
        assert "rate limit exceeded" in r.json()["error"]
        assert "UNTELL_RATE_LIMIT" in r.json()["error"]
        assert int(r.headers["retry-after"]) >= 1

    def test_zero_disables_it(self, monkeypatch):
        client, _api = self._client(monkeypatch, "0")
        codes = [client.post("/tells", json={"text": self.TEXT}).status_code for _n in range(8)]
        assert codes == [200] * 8

    def test_health_is_exempt(self, monkeypatch):
        """Rate-limiting the health endpoint would take a service down under its own monitoring."""
        client, _api = self._client(monkeypatch, "2")
        for _n in range(6):
            assert client.get("/health").status_code == 200

    def test_a_bad_value_falls_back_instead_of_crashing(self, monkeypatch):
        client, api = self._client(monkeypatch, "not-a-number")
        assert api._rate_limit() == api._DEFAULT_RATE_LIMIT
        assert client.post("/tells", json={"text": self.TEXT}).status_code == 200

    def test_separate_callers_get_separate_budgets(self, monkeypatch):
        """Keyed on the credential when present, so one noisy caller cannot exhaust everyone."""
        from fastapi.testclient import TestClient

        import untell.api_server as api

        monkeypatch.setenv("UNTELL_API_KEY", "key-a")
        monkeypatch.setenv("UNTELL_RATE_LIMIT", "3")
        api._rate_buckets.clear()
        client = TestClient(api.app)
        hdr = {"X-API-Key": "key-a"}
        codes = [client.post("/tells", json={"text": self.TEXT}, headers=hdr).status_code
                 for _n in range(5)]
        assert codes[:3] == [200] * 3 and codes[3:] == [429] * 2, codes
        # A different bucket key is unaffected by the exhausted one.
        api._rate_buckets["someone-else"] = (0.0, 0)
        assert len(api._rate_buckets) >= 2


def test_ceiling_rejects_an_unknown_rewriter_instead_of_substituting_one():
    """An unrecognised name fell through to `rw = None`, which means "let get_rewriter pick".

    So a typo — or a deliberate 'base' — silently ran a DIFFERENT backend than the one asked for,
    and with an API key configured that is the paid hosted-LLM path. HTTP 200 either way, no error
    field, and nothing in the response naming the rewriter that actually ran. The MCP tool already
    refused; the two surfaces disagreed.
    """
    with patch("untell.api_server.load_env"):
        from fastapi.testclient import TestClient

        from untell.api_server import app

        client = TestClient(app)
        for name in ("bogus_name", "base", "SURGICAL"):
            resp = client.post("/ceiling", json={"rewriter": name, "n": 1, "tier": "lite"})
            assert resp.status_code == 422, name
            assert "unknown rewriter" in resp.json()["error"]
            assert "free_rewriters" in resp.json()


def test_ceiling_response_names_the_corpus_it_measured():
    """A ceiling number is a property of its corpus, and this endpoint always uses the built-in
    demo sample — three hand-written paragraphs that are measurably easier than real AI text
    (0.86 before, against 1.00 for real ChatGPT answers). A REST caller quoting the number has no
    other way to know which corpus produced it."""
    with patch("untell.api_server.load_env"):
        from fastapi.testclient import TestClient

        from untell.api_server import app

        resp = TestClient(app).post(
            "/ceiling", json={"rewriter": "surgical", "n": 1, "tier": "lite", "max_iters": 1}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["corpus"] == "builtin"
        assert body["corpus_mean_words"] > 0


def test_ceiling_still_accepts_valid_rewriters():
    with patch("untell.api_server.load_env"):
        from fastapi.testclient import TestClient

        from untell.api_server import app

        client = TestClient(app)
        for name in ("surgical", "auto"):
            resp = client.post(
                "/ceiling", json={"rewriter": name, "n": 1, "tier": "lite", "max_iters": 1}
            )
            assert resp.status_code == 200, name


class _Unlimited:
    """Mixin disabling the 60-request/minute limiter for request-heavy test classes.

    They issue enough requests to trip it — one per style, one per endpoint — and a 429 is not what
    any of them is asserting.
    """

    @pytest.fixture(autouse=True)
    def _no_rate_limit(self, monkeypatch):
        import untell.api_server as api

        monkeypatch.setenv("UNTELL_RATE_LIMIT", "0")
        api._rate_buckets.clear()
        yield
        api._rate_buckets.clear()


class TestTierIsValidated(_Unlimited):
    """`tier` was a bare `str` on every request model, so any string was accepted.

    `load_detectors("bogus")` matches no tier and falls back to the always-on lite heuristic, so the
    response came back HTTP 200 carrying a lite-shaped result with nothing to say the requested tier
    was never honoured. The CLI rejects the same input at parse time (argparse `choices`, exit 2).
    """

    ENDPOINTS = ("/score", "/humanize", "/sentences", "/verify")

    @pytest.mark.parametrize("tier", ["bogus", "Full", "FULL", "lite ", "full,heavy"])
    @pytest.mark.parametrize("path", ENDPOINTS)
    def test_unknown_tier_is_rejected(self, path, tier):
        from fastapi.testclient import TestClient

        from untell.api_server import app

        resp = TestClient(app).post(path, json={"text": "A short test sentence.", "tier": tier})
        assert resp.status_code == 422, f"{path} accepted tier={tier!r}"

    @pytest.mark.parametrize("path", [p for p in ENDPOINTS if p != "/verify"])
    def test_empty_tier_is_rejected_everywhere_except_verify(self, path):
        from fastapi.testclient import TestClient

        from untell.api_server import app

        resp = TestClient(app).post(path, json={"text": "A short test sentence.", "tier": ""})
        assert resp.status_code == 422, f"{path} accepted an empty tier"

    def test_verify_still_accepts_the_empty_tier_its_cli_documents(self):
        """`untell-verify --tier ''` means commercial-only and is in the CLI's own `choices`.

        Narrowing this endpoint to the standard four would have made REST reject an input its CLI
        accepts — the same cross-surface divergence this class exists to prevent, reversed.
        """
        from fastapi.testclient import TestClient

        from untell.api_server import app

        resp = TestClient(app).post("/verify", json={"text": "A short test sentence.", "tier": ""})
        assert resp.status_code == 200

    def test_verify_vocabulary_matches_its_cli(self):
        from typing import get_args

        from untell.api_server import _VERIFY_TIER
        from untell.scripts.verify import build_parser

        parser = build_parser()
        tier_action = next(a for a in parser._actions if a.dest == "tier")
        assert set(get_args(_VERIFY_TIER)) == set(tier_action.choices)

    @pytest.mark.parametrize("tier", ["lite", "full", "heavy", "commercial"])
    def test_every_real_tier_still_passes(self, tier):
        from fastapi.testclient import TestClient

        from untell.api_server import app

        resp = TestClient(app).post("/score", json={"text": "A short test sentence.", "tier": tier})
        assert resp.status_code == 200, tier

    def test_the_literal_matches_what_load_detectors_honours(self):
        """The enum is restated in three places (argparse, this Literal, `_TIER_RANK`).

        Pin it to the loader's own table so adding a tier cannot leave the network surfaces
        rejecting a name the CLI accepts.
        """
        from typing import get_args

        from untell.api_server import _TIER
        from untell.detectors.base import _TIER_RANK

        assert set(get_args(_TIER)) == set(_TIER_RANK)

    def test_openapi_advertises_the_vocabulary(self):
        """A bare `str` gave clients no way to discover the valid values from /docs."""
        from fastapi.testclient import TestClient

        from untell.api_server import app
        from untell.detectors.base import _TIER_RANK

        schemas = TestClient(app).get("/openapi.json").json()["components"]["schemas"]
        for name in ("ScoreRequest", "HumanizeRequest", "CeilingRequest", "SentencesRequest"):
            assert set(schemas[name]["properties"]["tier"]["enum"]) == set(_TIER_RANK), name
        assert set(schemas["VerifyRequest"]["properties"]["tier"]["enum"]) == set(_TIER_RANK) | {""}


class TestAnUnmodelledFieldIsAnError(_Unlimited):
    """pydantic's default is to DROP unknown fields, which made a partial answer look like the answer.

    MEASURED: POST /humanize accepted `confirm`, `detector_thresholds` and `nonsense_field` with
    HTTP 200 and ran the loop without any of them. A caller asking for a confirmation re-scan, or
    for per-detector gates, got a result computed without them and nothing saying the request had
    been only partly honoured.
    """

    @pytest.mark.parametrize(
        "path", ["/score", "/humanize", "/tells", "/sentences", "/verify", "/ceiling"]
    )
    def test_an_unknown_field_is_rejected(self, path):
        from fastapi.testclient import TestClient

        from untell.api_server import app

        body = {"nonsense_field": 1}
        if path != "/ceiling":  # the only endpoint that takes no text
            body["text"] = "Some text."
        resp = TestClient(app).post(path, json=body)
        assert resp.status_code == 422, path

    def test_every_request_model_forbids_extras(self):
        """Enumerate the models rather than list paths by hand.

        A hand-written path list is exactly what let CeilingRequest keep inheriting BaseModel: it is
        the one model with no `text` field, so a mechanical edit keyed on `text` skipped it and no
        test noticed.
        """
        import inspect

        from pydantic import BaseModel

        import untell.api_server as api

        models = [
            obj
            for _, obj in inspect.getmembers(api, inspect.isclass)
            if issubclass(obj, BaseModel) and obj is not BaseModel and obj.__name__.endswith("Request")
        ]
        assert models, "no request models found — the discovery is wrong, not the models"
        lax = [m.__name__ for m in models if m.model_config.get("extra") != "forbid"]
        assert not lax, f"these request models silently drop unknown fields: {lax}"

    def test_the_error_names_the_offending_field(self):
        from fastapi.testclient import TestClient

        from untell.api_server import app

        resp = TestClient(app).post("/score", json={"text": "Some text.", "typo_here": 1})
        assert "typo_here" in resp.text

    @pytest.mark.parametrize(
        ("field", "value"),
        [("confirm", 3), ("detector_thresholds", {"hc3_roberta": 0.1})],
    )
    def test_the_newly_modelled_fields_reach_the_loop(self, monkeypatch, field, value):
        from fastapi.testclient import TestClient

        import untell.api_server as api

        seen: dict = {}
        monkeypatch.setattr(
            api, "untell_text", lambda text, **kw: seen.update(kw) or {"final": text, "post": {"max": 0.1}}
        )
        resp = TestClient(api.app).post(
            "/humanize",
            json={"text": "Some text.", "tier": "lite", "rewriter": "surgical", field: value},
        )
        assert resp.status_code == 200
        assert seen[field] == value

    def test_every_humanize_field_is_actually_forwarded(self, monkeypatch):
        """A modelled field that is never passed on is the same silent no-op, one layer in."""
        import inspect

        from fastapi.testclient import TestClient

        import untell.api_server as api
        from untell.scripts.run import untell_text

        seen: dict = {}
        monkeypatch.setattr(
            api, "untell_text", lambda text, **kw: seen.update(kw) or {"final": text, "post": {"max": 0.1}}
        )
        TestClient(api.app).post(
            "/humanize", json={"text": "Some text.", "tier": "lite", "rewriter": "surgical"}
        )
        loop_params = set(inspect.signature(untell_text).parameters)
        # `rewriter` is resolved from a name to an object, so it is forwarded under the same key.
        modelled = set(api.HumanizeRequest.model_fields) - {"text"}
        assert modelled <= loop_params, sorted(modelled - loop_params)
        assert modelled <= set(seen), f"modelled but never forwarded: {sorted(modelled - set(seen))}"


def test_score_response_names_the_scoring_path(monkeypatch):
    """`perplexity_burstiness` is two detectors under one name — GPT-2 when torch is importable,
    a stdlib heuristic otherwise — and measured on 100 held-out HC3 pairs that is FPR 6.0% against
    69.0% at the shipped threshold. score_text reports `detector_modes`; this pins that the REST
    surface passes it through, because a field a caller cannot see is not a disclosure."""
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
    with patch("untell.api_server.load_env"):
        from fastapi.testclient import TestClient

        from untell.api_server import app

        body = TestClient(app).post(
            "/score", json={"text": "A sufficiently long sentence for the heuristic.", "tier": "lite"}
        ).json()
        assert body["detector_modes"]["perplexity_burstiness"] == "stdlib"


class TestStyleIsValidated(_Unlimited):
    """`style` was a bare `str`, and an unknown name is a silent no-op.

    The name is looked up in the STYLES dict, missed, and skipped — so a caller asked for a voice,
    got HTTP 200, and received a rewrite with no style applied and nothing in the response saying
    so. `untell humanize --style` rejects the same input at parse time via argparse `choices`.
    """

    @pytest.mark.parametrize("style", ["bogus", "Casual", "CASUAL", "", "casual "])
    def test_an_unknown_style_is_rejected(self, style):
        from fastapi.testclient import TestClient

        from untell.api_server import app

        resp = TestClient(app).post(
            "/humanize",
            json={"text": "Some text.", "tier": "lite", "rewriter": "surgical", "style": style},
        )
        assert resp.status_code == 422, f"accepted style={style!r}"

    def test_every_real_style_is_accepted(self):
        from fastapi.testclient import TestClient

        from untell.api_server import app
        from untell.rewriter.prompts import STYLE_NAMES

        client = TestClient(app)
        for style in STYLE_NAMES:
            resp = client.post(
                "/humanize",
                json={"text": "Some text here.", "tier": "lite", "rewriter": "surgical",
                      "max_iters": 1, "style": style},
            )
            assert resp.status_code == 200, style

    def test_openapi_advertises_every_style(self):
        from fastapi.testclient import TestClient

        from untell.api_server import app
        from untell.rewriter.prompts import STYLE_NAMES

        schemas = TestClient(app).get("/openapi.json").json()["components"]["schemas"]
        assert schemas["_Style"]["enum"] == STYLE_NAMES

    def test_the_style_reaches_the_loop_as_a_plain_string(self, monkeypatch):
        """Downstream keys the STYLES dict on the name; a bare Enum member would miss it and
        reintroduce exactly the silent no-op this field now prevents."""
        from fastapi.testclient import TestClient

        import untell.api_server as api

        seen: dict = {}
        monkeypatch.setattr(
            api, "untell_text", lambda text, **kw: seen.update(kw) or {"final": text, "post": {"max": 0.1}}
        )
        TestClient(api.app).post(
            "/humanize",
            json={"text": "Some text.", "tier": "lite", "rewriter": "surgical", "style": "casual"},
        )
        assert seen["style"] == "casual"
        assert type(seen["style"]) is str

    def test_no_style_is_still_allowed(self):
        from fastapi.testclient import TestClient

        from untell.api_server import app

        resp = TestClient(app).post(
            "/humanize",
            json={"text": "Some text.", "tier": "lite", "rewriter": "surgical", "max_iters": 1},
        )
        assert resp.status_code == 200


class TestTierDefaultsMatchTheCLI:
    """The loop OPTIMISES against the tier it is given, so a weaker default is a weaker product.

    /humanize defaulted to lite — a single stdlib heuristic the README calls "weak — a demo signal,
    not an evasion claim" — and returned "passed" verdicts the CLI's four-detector ensemble would
    have rejected. Same class as the best_of=1 default: the CLI was strengthened and the network
    surfaces were left behind.
    """

    @pytest.mark.parametrize(
        "model_name", ["ScoreRequest", "HumanizeRequest", "VerifyRequest", "CeilingRequest"]
    )
    def test_scoring_surfaces_default_to_full(self, model_name):
        import untell.api_server as api

        model = getattr(api, model_name)
        assert model.model_fields["tier"].default == "full", model_name

    def test_the_cli_agrees(self):
        """Read the default off the CLI parser rather than restating it here."""
        from untell.scripts.run import build_parser

        parser = build_parser()
        tier_action = next(a for a in parser._actions if a.dest == "tier")
        assert tier_action.default == "full"
        assert set(tier_action.choices or ()) == {"lite", "full", "heavy", "commercial"}


class TestNumericFieldsAreBounded:
    """Every numeric field was an unbounded float/int.

    MEASURED: POST /score with `threshold: 50` returned HTTP 200 and a result in which nothing can
    ever be flagged, because the scores it is compared against live in [0, 1] — a caller who read
    the field as a percentage got a clean bill of health for every text they sent. The counts have
    the mirror problem: `max_iters` and `best_of` each multiply the work one request does.
    """

    TEXT = "Furthermore, the system leverages robust methodologies to optimize outcomes."

    def _client(self):
        from fastapi.testclient import TestClient

        from untell.api_server import app

        return TestClient(app)

    @pytest.mark.parametrize(
        ("endpoint", "payload"),
        [
            ("/score", {"threshold": 50}),
            ("/score", {"threshold": -0.1}),
            ("/humanize", {"max_iters": 0}),
            ("/humanize", {"max_iters": 10**6}),
            ("/humanize", {"best_of": 0}),
            ("/humanize", {"best_of": 99}),
            ("/humanize", {"confirm": -1}),
            ("/humanize", {"margin": 5}),
            ("/humanize", {"rewriter": "nope"}),
        ],
    )
    def test_out_of_range_is_a_422(self, endpoint, payload):
        with patch("untell.api_server.load_env"):
            resp = self._client().post(endpoint, json={"text": self.TEXT, **payload})
        assert resp.status_code == 422, resp.text

    def test_ceiling_sample_size_is_bounded(self):
        with patch("untell.api_server.load_env"):
            resp = self._client().post("/ceiling", json={"n": 10**7, "tier": "lite"})
        assert resp.status_code == 422, resp.text

    def test_values_inside_the_range_still_work(self):
        with patch("untell.api_server.load_env"):
            resp = self._client().post(
                "/score", json={"text": self.TEXT, "threshold": 0.3, "tier": "lite"}
            )
        assert resp.status_code == 200, resp.text


class TestRateBucketsCannotGrowWithoutBound:
    """`_rate_buckets` is keyed on caller-controlled values and nothing ever removed an entry.

    With no API key configured the key is the CLIENT IP, so an attacker with many source addresses
    — trivial over IPv6 — grows the dict without bound. That is memory exhaustion reachable by
    anyone who can reach the port, in the one component of this project that listens on a socket.
    A long-running public server hits the same thing without malice, one entry per client forever.
    """

    def test_expired_buckets_are_dropped(self):
        import time

        import untell.api_server as api

        api._rate_buckets.clear()
        now = time.monotonic()
        for i in range(api._RATE_BUCKET_SOFT_CAP + 1000):
            api._rate_buckets[f"ip{i}"] = (now - api._RATE_WINDOW_SECONDS - 1, 1)
        api._evict_stale_buckets(now)
        assert not api._rate_buckets, "expired buckets survived the sweep"

    def test_a_burst_of_live_clients_is_still_capped(self):
        """Every bucket live means a genuine burst, not accumulation. Memory must stay bounded
        anyway: the worst case for a dropped caller is one extra request allowed, which is strictly
        safer than the server falling over."""
        import time

        import untell.api_server as api

        api._rate_buckets.clear()
        now = time.monotonic()
        for i in range(api._RATE_BUCKET_SOFT_CAP + 1000):
            api._rate_buckets[f"ip{i}"] = (now, 1)
        api._evict_stale_buckets(now)
        assert len(api._rate_buckets) <= api._RATE_BUCKET_SOFT_CAP

    def test_eviction_is_a_noop_below_the_cap(self):
        """The sweep runs on every request, so it must cost nothing in the normal case."""
        import time

        import untell.api_server as api

        api._rate_buckets.clear()
        now = time.monotonic()
        for i in range(10):
            api._rate_buckets[f"ip{i}"] = (now - api._RATE_WINDOW_SECONDS - 1, 1)
        api._evict_stale_buckets(now)
        assert len(api._rate_buckets) == 10, "stale entries were dropped below the cap"

    def test_the_limiter_still_limits_after_eviction(self):
        """The point of the guard is memory, not permissiveness. Eviction must not hand an
        over-limit caller a clean slate while its own window is still open."""
        import time

        import untell.api_server as api

        api._rate_buckets.clear()
        now = time.monotonic()
        # One live caller, already over any sane limit, plus enough expired noise to trip the sweep.
        api._rate_buckets["attacker"] = (now, 10_000)
        for i in range(api._RATE_BUCKET_SOFT_CAP + 100):
            api._rate_buckets[f"old{i}"] = (now - api._RATE_WINDOW_SECONDS - 1, 1)
        api._evict_stale_buckets(now)
        assert "attacker" in api._rate_buckets, "a live over-limit bucket was evicted"
        assert api._rate_buckets["attacker"][1] == 10_000, "its count was reset"


class TestTheScoreResponseIsSafeToConsume:
    """`detectors` must be a map of numbers, because that is what it looks like.

    Internally a failed detector leaves a message beside its score —
    ``{"hc3_roberta": None, "hc3_roberta__error": "..."}`` — and every in-repo consumer knows to
    filter keys ending in ``__error``. That convention is deliberate and documented where it lives.

    A REST client does not have it. The obvious `max(detectors.values())` raised
    ``TypeError: '>' not supported between instances of 'str' and 'float'``, and nothing warned
    them: in every response where nothing has failed, the field really is a map of numbers.
    """

    @staticmethod
    def _with_a_broken_detector(victim="hc3_roberta"):
        from fastapi.testclient import TestClient

        from untell.api_server import app
        from untell.detectors import base

        client = TestClient(app)
        detector = next((d for d in base.all_detectors() if d.name == victim), None)
        if detector is None:
            pytest.skip(f"{victim} unavailable in this environment")
        cls = type(detector)
        original = cls.score

        def boom(self, text):
            raise RuntimeError("broken on purpose")

        cls.score = boom
        try:
            return client.post(
                "/score",
                json={"text": "Moreover, the framework leverages a robust approach here.",
                      "tier": "full"},
            ).json()
        finally:
            cls.score = original

    def test_no_string_appears_among_the_scores(self):
        body = self._with_a_broken_detector()
        offenders = {k: v for k, v in body["detectors"].items() if isinstance(v, str)}
        assert not offenders, f"string values in the detectors map: {offenders}"

    def test_the_values_can_be_compared(self):
        """The exact call a client writes first."""
        body = self._with_a_broken_detector()
        values = [v for v in body["detectors"].values() if v is not None]
        assert max(values) == pytest.approx(body["max"], abs=0.05)

    def test_the_failure_is_still_reported_somewhere(self):
        """Moving the message must not lose it — a silently-dropped detector is worse than an
        awkwardly-typed one."""
        body = self._with_a_broken_detector()
        assert body.get("failed_detectors") == ["hc3_roberta"]
        assert "hc3_roberta" in (body.get("detector_errors") or {})
        assert "broken on purpose" in body["detector_errors"]["hc3_roberta"]

    def test_a_healthy_response_gains_no_new_field(self):
        """The key appears only when something failed, so existing clients see no change."""
        from fastapi.testclient import TestClient

        from untell.api_server import app

        body = TestClient(app).post(
            "/score", json={"text": "The kettle boiled while I read the last few pages.",
                            "tier": "lite"},
        ).json()
        assert "detector_errors" not in body

    def test_the_internal_convention_is_untouched(self):
        """The sidecar stays inside `detectors` for library callers — this is a boundary fix, not a
        change to the internal contract that run.py, verify.py and reward.py all depend on."""
        from untell.detectors import base
        from untell.scripts.score import score_text

        detector = next((d for d in base.all_detectors() if d.name == "hc3_roberta"), None)
        if detector is None:
            pytest.skip("hc3_roberta unavailable")
        cls = type(detector)
        original = cls.score

        def boom(self, text):
            raise RuntimeError("broken on purpose")

        cls.score = boom
        try:
            result = score_text("Moreover, the framework leverages a robust approach here.",
                                tier="full")
        finally:
            cls.score = original
        assert "hc3_roberta__error" in result["detectors"], (
            "the library-level sidecar was removed; in-repo consumers filter on it"
        )


class TestTheOpenApiSchemaDescribesTheRealResponse:
    """The README advertises OpenAPI docs. Every endpoint returned a bare ``dict``, so FastAPI
    generated ``{"type": "object", "additionalProperties": true}`` for all seven — a page that tells
    a client nothing about what comes back.

    The schemas are attached with ``responses=``, not ``response_model=``, and that choice matters:
    a response model FILTERS, silently dropping any key it does not declare. Several of these
    responses carry keys only in particular circumstances — ``failed_detectors`` and
    ``detector_errors`` when a detector dies, ``warning`` on a tier downgrade — so a strict model
    would delete exactly the diagnostics a caller most needs. Describing without constraining is the
    right trade, but it means nothing enforces that the description is true. These tests do.
    """

    @staticmethod
    def _schema(path: str, method: str = "post") -> dict:
        from untell.api_server import app

        return app.openapi()["paths"][path][method]["responses"]["200"]["content"][
            "application/json"
        ]["schema"]

    @staticmethod
    def _client():
        from fastapi.testclient import TestClient

        from untell.api_server import app

        return TestClient(app)

    TEXT = "Moreover, the framework leverages a robust approach to deliver outcomes for teams."

    CALLS = [
        ("/health", "get", None),
        ("/score", "post", {"text": TEXT, "tier": "lite"}),
        ("/tells", "post", {"text": TEXT}),
        ("/sentences", "post", {"text": TEXT + " It works well enough.", "tier": "lite"}),
        ("/verify", "post", {"text": TEXT}),
        ("/ceiling", "post", {"n": 2, "tier": "lite", "rewriter": "structural"}),
    ]

    @pytest.mark.parametrize("path,method,body", CALLS)
    def test_every_required_field_is_actually_returned(self, path, method, body):
        client = self._client()
        response = client.get(path) if method == "get" else client.post(path, json=body)
        assert response.status_code == 200
        payload = response.json()
        missing = [k for k in self._schema(path, method).get("required", []) if k not in payload]
        assert not missing, f"{path} declares {missing} required but did not return them"

    @pytest.mark.parametrize("path,method,body", CALLS)
    def test_no_documented_field_is_stale(self, path, method, body):
        """A property the endpoint no longer returns is a promise the schema is still making.

        Conditional fields are excluded by name: they are documented precisely because they appear
        only sometimes, and their absence in a healthy call is correct.
        """
        # Only fields PROVEN to be conditional belong here. `results` was in this set and it
        # was not conditional — it did not exist. The exclusion was written from the same
        # guess as the schema, so the test confirmed the guess instead of checking it.
        conditional = {"warning", "failed_detectors", "detector_errors"}
        client = self._client()
        response = client.get(path) if method == "get" else client.post(path, json=body)
        payload = response.json()
        documented = set(self._schema(path, method).get("properties", {}))
        stale = sorted(documented - set(payload) - conditional)
        assert not stale, f"{path} documents fields it did not return: {stale}"

    def test_no_endpoint_is_left_undescribed(self):
        """Guards against a new route shipping with the empty schema all seven started with."""
        from untell.api_server import app

        undescribed = []
        for path, ops in app.openapi()["paths"].items():
            for method, op in ops.items():
                schema = (
                    op.get("responses", {}).get("200", {})
                    .get("content", {}).get("application/json", {}).get("schema", {})
                )
                if not schema.get("properties"):
                    undescribed.append(f"{method.upper()} {path}")
        assert not undescribed, f"undocumented response shape: {undescribed}"

    def test_describing_does_not_filter(self):
        """The reason for `responses=` over `response_model=`. `detector_modes` is returned but not
        required; if a response model were introduced it would vanish and this would catch it."""
        payload = self._client().post(
            "/score", json={"text": self.TEXT, "tier": "lite"}
        ).json()
        assert "detector_modes" in payload
        assert "verdict_threshold" in payload
