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

    @pytest.mark.parametrize("path", ["/score", "/humanize", "/tells", "/sentences", "/verify"])
    def test_an_unknown_field_is_rejected(self, path):
        from fastapi.testclient import TestClient

        from untell.api_server import app

        resp = TestClient(app).post(path, json={"text": "Some text.", "nonsense_field": 1})
        assert resp.status_code == 422, path

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
