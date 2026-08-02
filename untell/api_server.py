"""untell — production REST API server.

Built with FastAPI. Exposes the full humanizer surface as a JSON API with
API-key auth, rate limiting, and auto-generated OpenAPI docs at ``/docs``.

Quick start::

    pip install untell[server]
    UNTELL_API_KEY=secret untell-server

Or from source::

    pip install -e ".[server]"
    untell-server --reload

Endpoints:

- ``GET  /health``              — health check + detector tier info
- ``POST /score``               — score text with the local detector ensemble
- ``POST /humanize``            — run the closed-loop humanizer
- ``POST /tells``               — count AI writing tells
- ``POST /sentences``           — per-sentence AI flags
- ``POST /verify``              — pass/fail vs every configured checker
- ``POST /ceiling``             — measure the free evasion ceiling

All ``POST`` endpoints accept JSON with ``text`` (required) plus optional params.
See the ``/docs`` page for full schemas.
"""

from __future__ import annotations

import hmac
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from untell._env import load_env
from untell.scripts.run import untell_text
from untell.scripts.score import DEFAULT_THRESHOLD, MAX_INPUT_CHARS, score_text
from untell.scripts.sentences import score_sentences
from untell.scripts.tells import score_tells
from untell.scripts.verify import verify

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

APP_TITLE = "untell API"
APP_VERSION = "0.2.0"
APP_DESC = __doc__

# Free, no-key rewriter backends selectable via the ``rewriter`` field. Anything else (e.g. "auto")
# means "let get_rewriter pick a hosted/local-policy backend" and is passed as prefer=None below.
_FREE_REWRITERS = frozenset(
    {"surgical", "structural", "composite", "targeted", "neural", "ensemble", "max",
     "t5_paraphrase", "mt_pivot"}
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_env()
    yield


app = FastAPI(title=APP_TITLE, version=APP_VERSION, description=APP_DESC, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def _api_key() -> str:
    """Read the configured key per request rather than once at import.

    ``lifespan`` calls ``load_env()`` at *startup*, which happens after this module is imported.
    A key that lives only in ``.env`` — the workflow the docs describe — was therefore never
    visible to a module-level constant, and every check below fell through to the
    "no key configured = open access" branch. Cost of reading it here is one dict lookup.
    """
    return os.environ.get("UNTELL_API_KEY", "").strip()


def _verify_key(x_api_key: str | None = None) -> bool:
    key = _api_key()
    if not key:
        return True  # no key configured = open access
    # Constant-time: `==` on strings short-circuits at the first differing byte, so response time
    # leaks how long a supplied prefix matched and the key can be recovered a character at a time.
    return bool(x_api_key) and hmac.compare_digest(x_api_key, key)


def _check_auth(authorization: str | None, x_api_key: str | None) -> str | None:
    """Return an error message if auth fails, else None."""
    if not _api_key():
        return None
    if x_api_key and _verify_key(x_api_key):
        return None
    if authorization and authorization.startswith("Bearer ") and _verify_key(authorization[len("Bearer "):]):
        return None
    return "unauthorized — set UNTELL_API_KEY or pass X-API-Key / Authorization: Bearer <key>"


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


# Bound the text field on every request model. MEASURED: `preserve.lock()` runs BEFORE scoring and
# is uncapped, scaling ~45ms per KB after the spaCy model warms — 188 KB takes 8.5s, so roughly a
# megabyte occupies a worker for ~45s. score.py's 50k cap did not protect this path because it
# applies after locking. Rejecting at the edge turns an unbounded request into a 422 instead of a
# tied-up worker, and the bound is the scorer's own constant so the two cannot drift.
_TEXT = Field(..., max_length=MAX_INPUT_CHARS)


class ScoreRequest(BaseModel):
    text: str = _TEXT
    tier: str = "full"
    threshold: float = DEFAULT_THRESHOLD


class HumanizeRequest(BaseModel):
    text: str = _TEXT
    tier: str = "lite"
    threshold: float = DEFAULT_THRESHOLD
    style: str | None = None
    max_iters: int = 5
    # "composite", matching the CLI and the MCP tool. MEASURED: POST /humanize with defaults
    # returned "no rewriter configured" on any install without an API key, because "auto" is not
    # in _FREE_REWRITERS and auto-select declines to pick a backend without a key — even though
    # composite is free, always available, and the documented zero-dependency path.
    rewriter: str = "composite"
    # 3, matching the CLI's --best-of default. MEASURED over 6 real HC3 paragraphs:
    # best_of=1 -> 33% still flagged; best_of=3 -> 0%. The CLI moved to 3 after best-of-1 was
    # identified as a root cause of understated evasion; MCP and this surface were left behind.
    # (CeilingRequest stays at 1 — that matches eval/ceiling.py, where the single-draw baseline
    # is what is being measured.)
    best_of: int = 3
    margin: float = 0.0
    polish: bool = False


class TellsRequest(BaseModel):
    text: str = _TEXT
    include_matches: bool = False


class SentencesRequest(BaseModel):
    text: str = _TEXT
    tier: str = "lite"
    threshold: float = DEFAULT_THRESHOLD


class VerifyRequest(BaseModel):
    text: str = _TEXT
    threshold: float = DEFAULT_THRESHOLD
    tier: str = "full"
    sandbox: bool = False
    browser: str | None = None


class CeilingRequest(BaseModel):
    tier: str = "full"
    threshold: float = DEFAULT_THRESHOLD
    max_iters: int = 5
    rewriter: str = "surgical"
    best_of: int = 1
    n: int = 3


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe(result: dict) -> JSONResponse:
    if "error" in result:
        return JSONResponse(content=result, status_code=422)
    return JSONResponse(content=result)


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------
#
# The module docstring has advertised "rate limiting" since this server was written and nothing
# implemented it — there was no limiter, no 429, no counter. Retracting the claim was one option;
# making it true is the better one for a service that ships with auth and is described as
# production.
#
# Fixed window, in-process, no dependency. Keyed on the API key when one is presented, else the
# client address, so one noisy caller cannot exhaust everyone else's budget.
#
# HONEST LIMITATION: the counter lives in this process. Behind multiple uvicorn workers each has
# its own, so the effective limit is per worker, not global. That is fine for the single-process
# default this server documents and wrong for a horizontally-scaled deployment, which needs a
# shared store (Redis) — stated here rather than discovered later.
_RATE_WINDOW_SECONDS = 60
_DEFAULT_RATE_LIMIT = 60
_rate_buckets: dict[str, tuple[float, int]] = {}


def _rate_limit() -> int:
    """Requests allowed per window. 0 disables. Read per call so tests and ops can change it."""
    raw = os.environ.get("UNTELL_RATE_LIMIT", "").strip()
    if not raw:
        return _DEFAULT_RATE_LIMIT
    try:
        return max(0, int(raw))
    except ValueError:
        logger.warning("UNTELL_RATE_LIMIT=%r is not an integer; using %d", raw, _DEFAULT_RATE_LIMIT)
        return _DEFAULT_RATE_LIMIT


def _rate_limited(request: Request, credential: str) -> int | None:
    """Return seconds to wait if this caller is over the limit, else None."""
    limit = _rate_limit()
    if limit <= 0:
        return None
    import time

    # Prefer the credential: two callers behind one NAT are different clients, and one client
    # rotating source ports is not several.
    client = request.client.host if request.client else "unknown"
    bucket_key = credential or client

    now = time.monotonic()
    started, count = _rate_buckets.get(bucket_key, (now, 0))
    if now - started >= _RATE_WINDOW_SECONDS:
        started, count = now, 0
    count += 1
    _rate_buckets[bucket_key] = (started, count)
    if count > limit:
        return max(1, int(_RATE_WINDOW_SECONDS - (now - started)))
    return None


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


@app.middleware("http")
async def auth_middleware(request: Request, call_next) -> JSONResponse | Response:
    if request.url.path in ("/health", "/docs", "/openapi.json", "/redoc"):
        return await call_next(request)
    auth = request.headers.get("authorization")
    x_key = request.headers.get("x-api-key")
    err = _check_auth(auth, x_key)
    if err:
        return JSONResponse(content={"error": err}, status_code=401)

    # Rate limit AFTER auth, so an unauthenticated flood cannot consume a legitimate caller's
    # budget by sharing their bucket.
    retry_after = _rate_limited(request, x_key or auth or "")
    if retry_after is not None:
        return JSONResponse(
            content={
                "error": f"rate limit exceeded — {_rate_limit()} requests per "
                f"{_RATE_WINDOW_SECONDS}s. Set UNTELL_RATE_LIMIT to change it, 0 to disable."
            },
            status_code=429,
            headers={"Retry-After": str(retry_after)},
        )
    return await call_next(request)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
async def health() -> dict:
    """Health check. Returns service info and the available detector tier."""
    from untell.detectors.base import load_detectors, resolved_tier

    dets = load_detectors("full")
    return {
        "status": "ok",
        "version": APP_VERSION,
        "detector_tier": resolved_tier(dets),
        "detector_count": len(dets),
        "detectors": [d.name for d in dets],
    }


@app.post("/score")
async def score(body: ScoreRequest) -> dict:
    """Score text for AI-likelihood. Returns max, ai_percent, and per-detector breakdown."""
    return score_text(body.text, tier=body.tier, threshold=body.threshold)


@app.post("/humanize")
async def humanize(body: HumanizeRequest) -> JSONResponse:
    """Run the closed-loop humanizer. Returns the humanized text + before/after stats.

    The ``rewriter`` field controls which rewriting backend to use:
    - ``\"auto\"`` (default) — uses a hosted LLM if an API key is configured, else fails
    - ``\"composite\"`` — free structural + surgical chain ($0, no key)
    - ``\"neural\"`` — free T5 paraphrase + structural + surgical (needs .[full]; strongest free path)
    - ``\"surgical\"`` / ``\"structural\"`` / ``\"t5_paraphrase\"`` / ``\"mt_pivot\"`` — individual free backends
    """
    from untell.rewriter import get_rewriter

    # An unknown name used to fall through as None and then be silently auto-selected, so a typo
    # ran a DIFFERENT technique and the response reported it as the requested one. untell_text
    # resolves names itself and refuses to substitute, so hand it the name for anything not
    # free-listed. "auto" still means "let it choose", so that one keeps passing None.
    if body.rewriter in _FREE_REWRITERS:
        rw = get_rewriter(prefer=body.rewriter)
    else:
        rw = None if body.rewriter == "auto" else body.rewriter
    result = untell_text(
        body.text,
        tier=body.tier,
        threshold=body.threshold,
        style=body.style,
        max_iters=body.max_iters,
        rewriter=rw,
        best_of=body.best_of,
        margin=body.margin,
        polish=body.polish,
    )
    return _safe(result)


@app.post("/tells")
async def tells(body: TellsRequest) -> dict:
    """Count AI writing tells. Returns total count, rate per 100 words, and per-category breakdown."""
    return score_tells(body.text, include_matches=body.include_matches)


@app.post("/sentences")
async def sentences(body: SentencesRequest) -> dict:
    """Per-sentence AI scores. Flags the worst ~third of sentences for rewrite targeting."""
    return score_sentences(body.text, tier=body.tier, threshold=body.threshold)


@app.post("/verify")
async def verify_endpoint(body: VerifyRequest) -> dict:
    """Pass/fail vs every configured commercial checker plus the local detector ensemble."""
    browser_list = [s.strip() for s in body.browser.split(",")] if body.browser else None
    tier_arg: str | None = None if (body.tier or "").lower() in ("commercial", "") else body.tier
    return verify(body.text, threshold=body.threshold, sandbox=body.sandbox, browser=browser_list, tier=tier_arg)


@app.post("/ceiling")
async def ceiling(body: CeilingRequest) -> dict:
    """Measure untell's inference-only evasion ceiling against the local detector ensemble."""
    from eval.ceiling import _SAMPLE, measure_ceiling
    from untell.rewriter import get_rewriter

    # An unrecognised name used to fall through to `rw = None`, which means "let get_rewriter pick"
    # — so a typo, or a deliberate 'base', silently ran a DIFFERENT backend than the one asked for,
    # and with a key configured that is the paid hosted-LLM path. HTTP 200 either way, no error
    # field, nothing in the response naming the rewriter that actually ran. Reject instead; the MCP
    # tool already does the equivalent by passing the name through for untell_text to refuse.
    if body.rewriter not in _FREE_REWRITERS and body.rewriter != "auto":
        return JSONResponse(
            status_code=422,
            content={
                "error": f"unknown rewriter {body.rewriter!r}",
                "free_rewriters": sorted(_FREE_REWRITERS),
                "hint": "pass 'auto' to let the server choose a configured backend",
            },
        )
    rw = get_rewriter(prefer=body.rewriter) if body.rewriter in _FREE_REWRITERS else None
    # `n` was in the request schema but never used: passing texts=None ran the whole built-in
    # sample regardless, so a caller asking for one fast sample paid for all of them. Capped by
    # the sample size, and the response echoes the count actually measured.
    texts = list(_SAMPLE)[: max(1, body.n)]
    result = measure_ceiling(
        texts,
        tier=body.tier,
        threshold=body.threshold,
        max_iters=body.max_iters,
        rewriter=rw,
        best_of=body.best_of,
    )
    return result


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    import argparse

    import uvicorn

    parser = argparse.ArgumentParser(prog="untell-server")
    parser.add_argument("--host", default=os.environ.get("UNTELL_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("UNTELL_PORT", "8000")))
    parser.add_argument("--reload", action="store_true", help="auto-reload on file changes (dev)")
    args = parser.parse_args(argv)
    uvicorn.run("untell.api_server:app", host=args.host, port=args.port, reload=args.reload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
