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

import asyncio
import functools
import hmac
import logging
import os
from contextlib import asynccontextmanager
from enum import Enum
from typing import Annotated, Literal

# Named import failure. `untell-server` is a console script pointing at `main` in this module, so
# the module is imported before `main` can print anything — on a base (zero-dependency) install
# that surfaced as a bare `ModuleNotFoundError: No module named 'fastapi'` with a traceback, and
# nothing said which extra supplies it. `io_utils` already sets the standard here: name the package
# AND the extra ("reading it needs python-docx: pip install 'untell[docs]'").
#
# Still an ImportError, deliberately. A library caller that imports this module without the extra
# should get the exception its `try` expects, not a `SystemExit` that takes their process down.
try:
    from fastapi import FastAPI, Request
    from fastapi.middleware.cors import CORSMiddleware
except ModuleNotFoundError as _exc:  # pragma: no cover - exercised only on a base install
    raise ImportError(
        "the REST server needs FastAPI, which the base install does not ship: "
        "pip install 'untell[server]'. Everything else — the CLI, the MCP server and the Python "
        "API — works without it."
    ) from _exc
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field

from untell._env import load_env
from untell.rewriter.prompts import STYLE_NAMES
from untell.scripts.run import untell_text
from untell.scripts.score import (
    DEFAULT_THRESHOLD,
    MAX_INPUT_CHARS,
    score_text,
    split_detector_errors,
)
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


async def _warm_detectors() -> None:
    """Resolve the full detector list off the event loop, so `/health` is warm from the first call."""
    import asyncio as _asyncio

    from untell.detectors.base import load_detectors

    await _asyncio.to_thread(load_detectors, "full")


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_env()
    # Resolve the detector list before the server accepts traffic.
    #
    # `/health` reports it, and resolving it means calling `available()` on every detector, which
    # imports and probes the transformer stack. MEASURED on a cold process: the first /health took
    # 9.34s and the second 0.0026s — 3,636x. That first call is exactly the one an orchestrator
    # makes: the container starts, the probe fires, and a liveness timeout of 1-5s (the common
    # defaults) expires before the answer arrives. The process is then restarted, and restarted
    # again, having never served a request. `/health` was also the one endpoint not offloaded, so
    # those 9.34s blocked the event loop as well.
    #
    # Doing it here moves the cost to startup, where it belongs and where it is visible: uvicorn
    # does not accept connections until lifespan completes, so a probe either gets no connection
    # (unambiguous, and what startupProbe is for) or a fast answer. It never gets a slow one.
    #
    # Best-effort: a failure to warm must not stop the server, because /tells and /scrub need no
    # detectors at all and a user with a broken transformers install can still use them.
    try:
        await _warm_detectors()
    except Exception as exc:  # pragma: no cover - depends on the local install
        logger.warning("detector warm-up failed, /health will resolve them on demand: %s", exc)
    yield


app = FastAPI(title=APP_TITLE, version=APP_VERSION, description=APP_DESC, lifespan=lifespan)

# CORS. `allow_origins=["*"]` WITH `allow_credentials=True` is the combination the CORS spec
# forbids, and Starlette implements the forbidden case by REFLECTING the request's Origin header
# instead of sending `*` — because `*` is invalid alongside credentials. Reflecting it means any
# page the user happens to be visiting can call this server cross-origin with credentials attached
# and READ the response. On a server that ships an `UNTELL_API_KEY` auth path and runs on
# localhost by default, that is a browser tab away from someone else's text and settings.
#
# Secure by default, configurable when a caller genuinely needs cross-origin credentials:
#
#   unset            -> any origin may call, credentials NOT allowed (the spec-legal wildcard)
#   UNTELL_CORS_ORIGINS="https://a.example,https://b.example"
#                    -> exactly those origins, credentials allowed
#
# The default keeps the server usable from a scratch HTML page or another localhost port, which is
# what the wildcard was for, without also handing that page the user's credentialed session.
_CORS_ORIGINS = [o.strip() for o in os.environ.get("UNTELL_CORS_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS or ["*"],
    # Only ever True alongside an explicit origin list. Never with the wildcard.
    allow_credentials=bool(_CORS_ORIGINS),
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

# The CLI rejects an unknown --tier at parse time (argparse `choices`, exit 2). The network surfaces
# accepted anything: `load_detectors("bogus")` matches no tier, falls back to the lite heuristic, and
# the response comes back 200 with a lite-shaped result and no indication the requested tier was
# never honoured. A typo therefore produced a plausible answer from the wrong ensemble. Same
# vocabulary as the CLI, enforced at the edge.
_TIER = Literal["lite", "full", "heavy", "commercial"]

# /verify is the one surface whose vocabulary is wider: `untell-verify --tier ''` is a documented
# invocation meaning "commercial checkers only", and the handler already maps "" and "commercial" to
# the same local-skip. Narrowing this to _TIER would have made the REST surface reject an input its
# own CLI accepts — the same cross-surface divergence being fixed here, pointing the other way.
_VERIFY_TIER = Literal["lite", "full", "heavy", "commercial", ""]

# The CLI has `choices=STYLE_NAMES`. This field was a bare `str`, and an unrecognised name is looked
# up in the STYLES dict, missed, and silently ignored — so a caller asked for a voice, got HTTP 200,
# and received a rewrite with no style applied and nothing saying so. Built from STYLE_NAMES rather
# than restated, so the 14 modes cannot drift out of sync with the CLI or the MCP tool's docstring.
_Style = Enum("_Style", {name: name for name in STYLE_NAMES}, type=str)

# Every numeric field was an unbounded `float`/`int`. MEASURED: POST /score with `threshold: 50`
# returns HTTP 200 and a result in which nothing can ever be flagged, because the scores it is
# compared against live in [0, 1] — a caller who thought the field was a percentage got a clean
# bill of health for every text they sent. The counts have the mirror problem: `max_iters` and
# `best_of` each multiply the work a single request does, so an unbounded value is an open
# invitation to occupy a worker indefinitely, and a negative one silently means "do nothing".
#
# The bounds are the ones the flags already imply, enforced at the edge like `_TIER` and `_Style`.
# `threshold` is a probability. The upper limits on the counts are deliberately generous — they
# exist to stop a runaway, not to second-guess a caller.
_Probability = Annotated[float, Field(ge=0.0, le=1.0)]
_Iters = Annotated[int, Field(ge=1, le=100)]
_BestOf = Annotated[int, Field(ge=1, le=32)]
_Confirm = Annotated[int, Field(ge=0, le=32)]
_SampleN = Annotated[int, Field(ge=1, le=1000)]

# The CLI validates --rewriter against this list; this field was a bare `str`. An unknown name
# reaches `get_rewriter(prefer=...)`, which returns the "rewriter is not available" error dict —
# a 200 response whose body says the request failed, where the CLI exits 2 at parse time.
_Rewriter = Literal[
    "auto", "surgical", "structural", "composite", "targeted", "neural", "ensemble",
    "max", "t5_paraphrase", "mt_pivot", "base",
]


class _Request(BaseModel):
    """Base for every request model: an unmodelled field is an ERROR, not a silent drop.

    pydantic's default is to ignore unknown fields. MEASURED: POST /humanize accepted `confirm`,
    `detector_thresholds` and even `nonsense_field` with HTTP 200, and the loop ran without any of
    them — so a caller asking for a 3-way confirmation re-scan, or per-detector gates, got back a
    result computed without them and nothing to say the request was only partly honoured. That is
    worse than a rejection: the response looks like the answer to the question that was asked.

    This makes an unsupported parameter a 422 naming the field. Clients sending fields this API
    never modelled will now get an error where they previously got a quietly different computation.
    """

    model_config = ConfigDict(extra="forbid")


class ScoreRequest(_Request):
    text: str = _TEXT
    tier: _TIER = "full"
    threshold: _Probability = DEFAULT_THRESHOLD


class HumanizeRequest(_Request):
    text: str = _TEXT
    # "full", matching the CLI's `--tier` default. The loop OPTIMISES against whatever tier it is
    # given, so defaulting to lite meant every REST caller drove a single stdlib heuristic — which
    # the README describes as "weak — a demo signal, not an evasion claim" — and got back a "passed"
    # verdict the CLI's four-detector ensemble would have rejected. Same shape as the best_of=1
    # default fixed below: the CLI was strengthened and the network surfaces were left behind.
    tier: _TIER = "full"
    threshold: _Probability = DEFAULT_THRESHOLD
    style: _Style | None = None
    max_iters: _Iters = 5
    # "composite", matching the CLI and the MCP tool. MEASURED: POST /humanize with defaults
    # returned "no rewriter configured" on any install without an API key, because "auto" is not
    # in _FREE_REWRITERS and auto-select declines to pick a backend without a key — even though
    # composite is free, always available, and the documented zero-dependency path.
    rewriter: _Rewriter = "composite"
    # 3, matching the CLI's --best-of default. MEASURED over 6 real HC3 paragraphs:
    # best_of=1 -> 33% still flagged; best_of=3 -> 0%. The CLI moved to 3 after best-of-1 was
    # identified as a root cause of understated evasion; MCP and this surface were left behind.
    # (CeilingRequest stays at 1 — that matches eval/ceiling.py, where the single-draw baseline
    # is what is being measured.)
    best_of: _BestOf = 3
    margin: _Probability = 0.0
    polish: bool = False
    # Both are `untell humanize` flags that this surface modelled nowhere, so sending them was a
    # silent no-op. `confirm` re-scores a pass N more times and keeps "passed" only if every re-scan
    # clears — the guard against a noisy detector re-flagging. `detector_thresholds` holds named
    # detectors to their own stricter gates on top of the global threshold. Neither needs an extra
    # dependency, and both change the verdict, which is precisely why dropping them quietly was
    # worse than refusing them.
    confirm: _Confirm = 0
    detector_thresholds: dict[str, float] | None = None
    # The CLI takes a FILE path here; over HTTP the sample travels as text. Among candidate
    # rewrites already tied on AI tells, the one whose sentence length, rhythm and comma rate sit
    # closest to this wins — a tie-break inside the 0.02 detector noise band: no cost in AI tells,
    # and up to 0.02 of detector score (measured 0.009 at worst, on 3 of 12). See scripts/voice.py
    # for what it does and does not claim to measure.
    voice_sample: str | None = Field(default=None, max_length=MAX_INPUT_CHARS)
    # Unset derives the stream from the text, so an identical request already returns an identical
    # result. Sent as an int it fixes the stream, which is what makes two requests that differ by
    # one field comparable — otherwise the difference between them includes the draw.
    seed: int | None = None


class TellsRequest(_Request):
    text: str = _TEXT
    include_matches: bool = False


class ScrubRequest(_Request):
    text: str = _TEXT


class SentencesRequest(_Request):
    text: str = _TEXT
    tier: _TIER = "lite"
    threshold: _Probability = DEFAULT_THRESHOLD


class VerifyRequest(_Request):
    text: str = _TEXT
    threshold: _Probability = DEFAULT_THRESHOLD
    tier: _VERIFY_TIER = "full"
    sandbox: bool = False
    browser: str | None = None


class CeilingRequest(_Request):
    # `_Request`, not `BaseModel`. This is the one request model with no `text` field, so it was the
    # one a mechanical edit over `text: str = _TEXT` missed — and it kept silently dropping unknown
    # fields after every other endpoint had stopped.
    tier: _TIER = "full"
    threshold: _Probability = DEFAULT_THRESHOLD
    max_iters: _Iters = 5
    # Deliberately NOT `_Rewriter`. /ceiling's handler validates against `_FREE_REWRITERS`, a
    # narrower set than the CLI's: "base" and "auto" reach the paid hosted path, and a measurement
    # endpoint that quietly bills is worse than one that refuses. It answers with its own
    # "unknown rewriter" message naming the free names, which a Literal here would pre-empt.
    rewriter: str = "surgical"
    best_of: _BestOf = 1
    n: _SampleN = 3


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

# The bucket dict is keyed on caller-controlled values — the API key when one is configured, and
# otherwise the CLIENT IP — and nothing ever removed an entry. A long-running public server
# therefore accumulates one entry per distinct client forever, and an attacker with many source
# addresses (trivial over IPv6) grows it without bound. That is memory exhaustion reachable by
# anyone who can reach the port, in the one component of this project that listens on a socket.
#
# Eviction is opportunistic rather than a background task: a sweep runs when the dict crosses the
# soft cap, dropping every bucket whose window has already expired. Expired buckets are dead
# weight — `_rate_limited` resets any bucket older than the window on its next hit — so removing
# them changes no decision the limiter makes.
_RATE_BUCKET_SOFT_CAP = 4096


def _evict_stale_buckets(now: float) -> None:
    """Drop buckets whose window has expired. No-op below the soft cap."""
    if len(_rate_buckets) <= _RATE_BUCKET_SOFT_CAP:
        return
    stale = [k for k, (started, _n) in _rate_buckets.items() if now - started >= _RATE_WINDOW_SECONDS]
    for k in stale:
        del _rate_buckets[k]
    # Still over the cap means every bucket is live — a genuine burst of distinct clients rather
    # than accumulation. Drop the oldest so memory stays bounded; the worst case for a dropped
    # caller is one extra request allowed, which is strictly safer than the server falling over.
    if len(_rate_buckets) > _RATE_BUCKET_SOFT_CAP:
        for k, _v in sorted(_rate_buckets.items(), key=lambda kv: kv[1][0])[
            : len(_rate_buckets) - _RATE_BUCKET_SOFT_CAP
        ]:
            del _rate_buckets[k]


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
    _evict_stale_buckets(now)
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


# --- documented response shapes ------------------------------------------------------------------
# Every endpoint returns a bare ``dict``, so FastAPI generated `{"type": "object",
# "additionalProperties": true}` for all seven — that is, the OpenAPI page the README advertises
# told a client nothing whatsoever about what comes back.
#
# Attached with ``responses=`` rather than ``response_model=`` on purpose. A response model FILTERS:
# any key not declared is silently dropped from the payload. Several of these responses carry keys
# only in particular circumstances — ``failed_detectors`` and ``detector_errors`` appear when a
# detector dies, ``warning`` when the tier is downgraded — and a strict model would delete exactly
# the diagnostics a caller most needs, turning a documentation improvement into data loss. These
# describe without constraining.
def _obj(description: str, properties: dict, *, required: list[str] | None = None) -> dict:
    return {
        200: {
            "description": description,
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": properties,
                        "required": required or [],
                        "additionalProperties": True,
                    }
                }
            },
        }
    }


_NUM = {"type": "number"}
_STR = {"type": "string"}
_BOOL = {"type": "boolean"}
_INT = {"type": "integer"}
_SCORE_MAP = {
    "type": "object",
    "additionalProperties": {"type": ["number", "null"]},
    "description": "detector name -> P(AI) in [0,1], or null when that detector produced no score",
}

_HEALTH_RESPONSES = _obj(
    "Service and detector-stack status.",
    {
        "status": _STR, "version": _STR, "detector_tier": _STR, "detector_count": _INT,
        "detectors": {"type": "array", "items": _STR},
    },
    required=["status", "version"],
)

_SCORE_RESPONSES = _obj(
    "AI-likelihood for the text.",
    {
        "tier": {**_STR, "description": "the tier that actually produced numbers"},
        "tier_requested": {**_STR, "description": "what was asked for; differs when detectors failed"},
        "detectors": _SCORE_MAP,
        "detector_errors": {
            "type": "object", "additionalProperties": _STR,
            "description": "present only when a detector raised: name -> message",
        },
        "failed_detectors": {
            "type": "array", "items": _STR,
            "description": "present only when a detector raised",
        },
        "detector_modes": {
            "type": "object", "additionalProperties": _STR,
            "description": "which scoring path ran, where a detector has more than one",
        },
        "max": {**_NUM, "description": "highest P(AI) across detectors — the headline number"},
        "mean": _NUM,
        "ai_percent": {**_NUM, "description": "max * 100"},
        "threshold": {**_NUM, "description": "the value supplied by the caller"},
        "verdict_threshold": {
            **_NUM,
            "description": "the calibrated bar `flagged` is decided on; not always `threshold`",
        },
        "flagged": _BOOL,
        "warning": {**_STR, "description": "present only when the effective tier was downgraded"},
    },
    required=["tier", "detectors", "max", "ai_percent", "flagged"],
)

_TELLS_RESPONSES = _obj(
    "Mechanical AI-tell counts. Lower is more human-reading.",
    {
        "words": _INT, "tells": _INT, "tells_per_100w": _NUM,
        "by_category": {"type": "object", "additionalProperties": _INT},
        "by_evidence": {
            "type": "object", "additionalProperties": _INT,
            "description": "counts split by how incriminating the category is: strong/moderate/weak",
        },
        "burstiness_cv": {"type": ["number", "null"]},
        "low_burstiness": _BOOL,
        "language_supported": {
            **_BOOL,
            "description": "false when the text is mostly a script this English catalogue "
                           "cannot match; the counts are then not evidence of anything",
        },
        # Returned all along and documented nowhere, so an API consumer reading the spec had no
        # reason to look for the one field that says the numbers above it mean nothing.
        "warning": {
            **_STR,
            "description": "present when the counts should not be read at face value — text with "
                           "no letters at all, or mostly in a script this catalogue cannot match",
        },
        # The same omission as `warning` above, one field over: `include_matches=true` has always
        # returned this and the schema never mentioned it, so a client generated from the spec
        # would drop the only field that says WHICH phrases were counted. Absent when the flag is
        # not set, which is why it is not in `required`.
        "matches": {
            "type": "object",
            "additionalProperties": {"type": "array", "items": _STR},
            "description": "present only when include_matches=true: category -> the exact phrases "
                           "counted under it, so a caller can see what drove the number rather "
                           "than trusting it",
        },
    },
    required=["words", "tells", "tells_per_100w", "by_category", "language_supported"],
)

_SCRUB_RESPONSES = _obj(
    "Text with hidden watermark characters removed, and how many there were.",
    {
        "clean": {**_STR, "description": "the text with the hidden characters stripped"},
        "hidden_chars_removed": {
            **_INT,
            "description": "how many were found in the SUBMITTED text; 0 means it was already "
                           "clean, which is itself worth knowing",
        },
    },
    required=["clean", "hidden_chars_removed"],
)

_SENTENCES_RESPONSES = _obj(
    "Per-sentence scores and the sentences worth rewriting.",
    {
        "tier": _STR, "threshold": _NUM,
        "sentences": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
        "flagged": {"type": "array", "items": _STR},
        "note": {**_STR, "description": "caveat about what this tier's targeting is worth"},
        # Not the same thing as `note`, which is always present and is about per-sentence noise in
        # general. This appears only when the configured tier cannot rank sentences at all —
        # MEASURED, the pure-stdlib path returns 6 distinct values across 100 sentences, 91 of them
        # exactly 0.250, AUROC 0.515 against 0.965 at the full tier.
        "warning": {
            **_STR,
            "description": "present when the configured tier's per-sentence ranking is near-chance "
                           "(the pure-stdlib path). The `flagged` list is then close to arbitrary",
        },
        # A different question from `warning`, and the reason both exist: `warning` says the
        # DETECTOR cannot rank, this says THIS DOCUMENT's scores are too close together to order,
        # whichever detector produced them. MEASURED at tier=full, within-document spread of
        # per-sentence max: 0.0088 mean on HC3 against 0.6595 on RAID, with two HC3 documents in
        # eight scoring every sentence at exactly 0.9992.
        "unrankable": {
            "type": "boolean",
            "description": "present and true when this document's per-sentence scores span less "
                           "than 0.05, so `flagged` is close to whichever order the sort produced. "
                           "Rewrite the whole passage rather than the flagged spans",
        },
    },
    required=["tier", "sentences", "flagged"],
)

_VERIFY_RESPONSES = _obj(
    "Commercial-detector verification. Only detectors with a configured key are consulted.",
    {
        "configured": {"type": "array", "items": _STR},
        "threshold": _NUM,
        "results": {"type": "object", "additionalProperties": True},
        # `passes_all` is False when NOTHING ran, not only when something failed: it is
        # `bool(names) and all(...)`, which is False for an empty checker set. That is the
        # conservative choice — refusing to report a pass nobody verified — but it means a
        # consumer reading the boolean alone cannot tell "the text failed" from "no checker was
        # configured". The CLI says so in words; a machine client only has this schema.
        "passes_all": {
            **_BOOL,
            "description": (
                "true only if every configured checker passed. FALSE when n_configured is 0 — "
                "nothing ran, which is not a verdict on the text. Check n_configured first."
            ),
        },
        "n_configured": {**_INT, "description": "how many checkers actually ran; 0 means none"},
        "n_passing": _INT,
        "warning": {
            **_STR,
            "description": (
                "present only when the text carries invisible characters or homoglyph "
                "substitution. These no longer move the score — the detectors normalise them, "
                "verified at 0.0000 on both tiers — but they are still in the submitted text and "
                "another tool may read them differently."
            ),
        },
    },
    required=["configured", "passes_all", "n_configured"],
)

_HUMANIZE_RESPONSES = _obj(
    "The rewritten text plus before/after evidence.",
    {
        "final": {**_STR, "description": "the rewritten text — this is the output"},
        "iterations": _INT, "rewrites": _INT, "adopted": _INT, "changed": _BOOL,
        "pre": {"type": "object", "additionalProperties": True, "description": "score before"},
        "post": {"type": "object", "additionalProperties": True, "description": "score after"},
        "similarity": {**_NUM, "description": "meaning similarity against the source"},
        "sim_bar": _NUM, "quality_metric": _STR,
        "meaning_gate": {
            **_STR,
            "description": "which fidelity checks were in force: 'nli' (all of them), 'nli (no "
                           "role check)' when spaCy's model is missing, or a 'similarity-only' "
                           "fallback when the NLI stack is unavailable or the veto is disabled. "
                           "MEASURED over 49 real rewrites, the role check supplied 2 of the 3 "
                           "vetoes the full conjunction produced, so the middle value is not a "
                           "detail",
        },
        "tier": _STR, "flagged": _BOOL,
        "stopped": {**_STR, "description": "why the loop stopped"},
        # The caveats a machine client has no other channel for. `pre` and `post` can be identical
        # to four decimals on text that measurably improved — MEASURED, tells/100w 3.80 -> 2.98 with
        # `max` pinned at 0.9997 either side — and this is the only field that says so.
        "warning": {
            **_STR,
            "description": "present when the numbers need a caveat: the text carried invisible "
                           "characters, no detector could score it, or the hardest detector is "
                           "pinned so the before/after P(AI) comparison cannot move. Several are "
                           "joined with 'Also:'",
        },
        # `seed` and the tell counts. The loop grew all three and this schema did not, which is
        # the drift docs/result-shapes.md had in the same week — a documented surface enumerating
        # fields cannot be left to catch up on its own, because nothing complains.
        #
        # The tell counts pair directly with the `warning` above: when the hardest detector is
        # pinned, "P(AI) 1.00 -> 1.00" is the whole before/after story a client can see, and these
        # are the numbers that did move. MEASURED on 4 HC3 documents at full tier, max gained
        # +0.0000 on 4 of 4 while tells fell 4->0, 1->0 and 1->0.
        "seed": {
            **_INT,
            "description": "the random stream this run used. Unset in the request, it is derived "
                           "from the text; send it back to reproduce the run exactly",
        },
        "tells_before": {**_INT, "description": "AI writing tells counted in the input"},
        "tells_after": {
            **_INT,
            "description": "AI writing tells counted in the output. On a corpus where the "
                           "detectors saturate this is the only before/after pair that moves",
        },
        "voice_warning": {
            **_STR,
            "description": "present when a voice sample was supplied but could not be used",
        },
        "rewriter_warning": {
            **_STR,
            "description": "present when the requested rewriter was not the one that ran — today "
                           "that means no hosted or local-policy backend was configured and the "
                           "free 'composite' path ran instead",
        },
    },
    required=["final", "changed", "pre", "post", "flagged"],
)

# Written from an actual call, unlike the first version of this one — which documented a `results`
# object the endpoint has never returned and omitted twenty fields it does. It passed its own
# staleness test because `results` was in that test's conditional-exclusion list, which I had
# written from the same guess. A schema and its test drawn from the same assumption check nothing.
_CEILING_RESPONSES = _obj(
    "Measured evasion ceiling over a sample: before/after scores and what produced them.",
    {
        "n": {**_INT, "description": "documents actually measured"},
        "corpus": _STR,
        "corpus_mean_words": _NUM,
        "rewriter": _STR,
        "rewriter_available": {
            **_BOOL,
            "description": "false means the requested backend could not load and nothing was "
                           "rewritten — check this before reading the numbers",
        },
        "tier": _STR,
        "threshold": _NUM,
        "max_iters": _INT,
        "best_of": _INT,
        "repeats": {**_INT, "description": "how many times the whole run was repeated"},
        "run_post_means": {
            "type": "array", "items": _NUM,
            "description": "one post mean per repeat; the spread across these is the noise floor",
        },
        "post_mean_max_stdev": {
            "type": ["number", "null"],
            "description": "null when repeats < 2, i.e. when there is no spread to report",
        },
        "pre_mean_max": _NUM,
        "post_mean_max": {**_NUM, "description": "the headline: mean max P(AI) after rewriting"},
        "pre_flagged_rate": _NUM,
        "post_flagged_rate": _NUM,
        "rewrote": {**_INT, "description": "documents the rewriter actually changed"},
        "unscored": {**_INT, "description": "documents no detector could score"},
        "mean_similarity": _NUM,
        "min_similarity": {**_NUM, "description": "the worst single document, not the average"},
        "per_detector_pre": _SCORE_MAP,
        "per_detector_post": _SCORE_MAP,
    },
    required=["n", "tier", "rewriter", "pre_mean_max", "post_mean_max", "rewriter_available"],
)


@app.get("/health", responses=_HEALTH_RESPONSES)
async def health() -> dict:
    """Health check. Returns service info and the available detector tier."""
    from untell.detectors.base import load_detectors, resolved_tier

    # Offloaded like every other worker. Warm this is microseconds, but `available()` on the
    # transformer detectors is not guaranteed to stay warm — a torn-down model cache or a first
    # call that outran the startup warm-up would otherwise block the loop, and this is the one
    # endpoint whose whole job is to answer promptly.
    dets = await _offload(load_detectors, "full")
    return {
        "status": "ok",
        "version": APP_VERSION,
        "detector_tier": resolved_tier(dets),
        "detector_count": len(dets),
        "detectors": [d.name for d in dets],
    }


def _numeric_detectors(result: dict) -> dict:
    """Kept as the name the API tests use; the implementation is shared.

    It moved to `untell/scripts/score.py` when the same defect turned up on `/humanize`, whose
    `pre` and `post` are score dicts of their own and were going out with `name__error` strings
    mixed in among the floats. One definition, three callers — this endpoint, /humanize, and the
    MCP score tool, which normalised nothing at all.
    """
    return split_detector_errors(result)


async def _offload(fn, *args, **kwargs):
    """Run a blocking worker off the event loop.

    Every endpoint here is `async def` and used to call its worker DIRECTLY, so the work ran on the
    event loop and nothing else could be served until it returned. MEASURED against an 11.20s
    /humanize with /health polled every 20ms throughout: 2 health responses before it started, 0
    DURING, 1 after. A liveness probe with any timeout under 11 seconds fails, and an orchestrator
    acting on that restarts the process mid-request.

    Per-call latency cannot show this and the first attempt to measure it used exactly that
    statistic: a blocked loop makes the polls queue and then complete quickly once the rewrite
    returns, which reads as a healthy 2.8ms median. What separates the two is WHEN each response
    lands relative to the rewrite, not how long each took.

    This does NOT make concurrent rewrites parallel. `untell_text` holds a process-wide lock around
    its seeded region (see run.py) because it seeds the global `random` module, so two rewrites
    still serialise — they just serialise off the event loop instead of on it. Offloading before
    that lock existed would have traded a blocked server for irreproducible output.
    """
    return await asyncio.to_thread(functools.partial(fn, *args, **kwargs))


@app.post("/score", responses=_SCORE_RESPONSES)
async def score(body: ScoreRequest) -> dict:
    """Score text for AI-likelihood. Returns max, ai_percent, and per-detector breakdown."""
    return _numeric_detectors(
        await _offload(score_text, body.text, tier=body.tier, threshold=body.threshold)
    )


@app.post("/humanize", responses=_HUMANIZE_RESPONSES)
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
    result = await _offload(
        untell_text,
        body.text,
        tier=body.tier,
        threshold=body.threshold,
        # `str(...)` on the enum member, not the member itself — downstream does a dict lookup on
        # STYLES and a bare Enum would miss it, reintroducing the silent no-op this field now
        # prevents. (`type=str` makes it a str subclass, but the value is what STYLES is keyed on.)
        style=body.style.value if body.style is not None else None,
        max_iters=body.max_iters,
        rewriter=rw,
        best_of=body.best_of,
        margin=body.margin,
        polish=body.polish,
        confirm=body.confirm,
        detector_thresholds=body.detector_thresholds,
        voice_sample=body.voice_sample,
        seed=body.seed,
    )
    return _safe(_numeric_detectors(result))


@app.post("/tells", responses=_TELLS_RESPONSES)
async def tells(body: TellsRequest) -> dict:
    """Count AI writing tells. Returns total count, rate per 100 words, and per-category breakdown."""
    return score_tells(body.text, include_matches=body.include_matches)


@app.post("/scrub", responses=_SCRUB_RESPONSES)
async def scrub(body: ScrubRequest) -> dict:
    """Strip hidden watermark, zero-width and homoglyph characters. Returns the cleaned text.

    The CLI has `untell-scrub` and the MCP server has a `scrub` tool; this surface had neither, so
    a REST caller holding untrusted text had no way to clean it. That is the one asymmetry in the
    surface matrix that costs a caller something they cannot work around: the characters do not move
    THIS ensemble's score — normalised, verified at 0.0000 on both tiers — but the same text took an
    external detector from 0.0002 to 0.7900 on those bytes alone.
    """
    from untell.attacks import count_hidden, scrub_hidden

    return {"clean": scrub_hidden(body.text), "hidden_chars_removed": count_hidden(body.text)}


@app.post("/sentences", responses=_SENTENCES_RESPONSES)
async def sentences(body: SentencesRequest) -> dict:
    """Per-sentence AI scores. Flags the worst ~third of sentences for rewrite targeting."""
    return await _offload(
        score_sentences, body.text, tier=body.tier, threshold=body.threshold
    )


@app.post("/verify", responses=_VERIFY_RESPONSES)
async def verify_endpoint(body: VerifyRequest) -> dict:
    """Pass/fail vs every configured commercial checker plus the local detector ensemble."""
    browser_list = [s.strip() for s in body.browser.split(",")] if body.browser else None
    tier_arg: str | None = None if (body.tier or "").lower() in ("commercial", "") else body.tier
    return await _offload(
        verify, body.text, threshold=body.threshold, sandbox=body.sandbox,
        browser=browser_list, tier=tier_arg,
    )


@app.post("/ceiling", responses=_CEILING_RESPONSES)
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
    result = await _offload(
        measure_ceiling,
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
