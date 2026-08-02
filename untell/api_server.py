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
from pydantic import BaseModel

from untell._env import load_env
from untell.scripts.run import untell_text
from untell.scripts.score import DEFAULT_THRESHOLD, score_text
from untell.scripts.sentences import score_sentences
from untell.scripts.tells import score_tells
from untell.scripts.verify import verify

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


class ScoreRequest(BaseModel):
    text: str
    tier: str = "full"
    threshold: float = DEFAULT_THRESHOLD


class HumanizeRequest(BaseModel):
    text: str
    tier: str = "lite"
    threshold: float = DEFAULT_THRESHOLD
    style: str | None = None
    max_iters: int = 5
    rewriter: str = "auto"
    best_of: int = 1
    margin: float = 0.0
    polish: bool = False


class TellsRequest(BaseModel):
    text: str
    include_matches: bool = False


class SentencesRequest(BaseModel):
    text: str
    tier: str = "lite"
    threshold: float = DEFAULT_THRESHOLD


class VerifyRequest(BaseModel):
    text: str
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

    rw = get_rewriter(prefer=body.rewriter) if body.rewriter in _FREE_REWRITERS else None
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
    from eval.ceiling import measure_ceiling
    from untell.rewriter import get_rewriter

    rw = get_rewriter(prefer=body.rewriter) if body.rewriter in _FREE_REWRITERS else None
    result = measure_ceiling(
        None,
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
