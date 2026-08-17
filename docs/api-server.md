# API Server

untell ships a production-grade REST API server built with **FastAPI** — auto-generated OpenAPI docs,
API-key auth, CORS support, and the full scoring, analysis and rewriting surface from the CLI.

## Quick start

```bash
pip install "untell[server]"
UNTELL_API_KEY=my-secret-key untell-server
```

Open **http://localhost:8000/docs** for the interactive API documentation.

### Hosted-LLM rewriters

The `/humanize` endpoint can delegate rewriting to a hosted LLM (Anthropic or OpenAI) instead of
the bundled local backends. Those providers are optional and install with the `api` extra:

```bash
pip install "untell[api]"
```

The adapters are key-gated at runtime: set `ANTHROPIC_API_KEY` (or `OPENAI_API_KEY`) and the
rewriter becomes available. The request model only accepts the CLI's rewriter names, so a hosted
provider is reached through `rewriter: "auto"` — it picks a hosted provider automatically when a
key is set and falls back to the free local composite path otherwise. (`rewriter: "anthropic"` /
`"openai"` themselves are rejected with `422` at the edge.)

## Configuration

| Env var | Default | Description |
|---|---|---|
| `UNTELL_API_KEY` | *(none)* | API key for auth. Unset **or empty** = open access. |
| `UNTELL_RATE_LIMIT` | `60` | Requests per 60s per caller. `0` disables. |
| `UNTELL_HOST` | `127.0.0.1` | Bind address |
| `UNTELL_PORT` | `8000` | Port |
| `UNTELL_CORS_ORIGINS` | *(none)* | Comma-separated origins allowed cross-origin **with credentials**. Unset = any origin may call, credentials NOT allowed (the spec-legal wildcard); setting a list restricts to exactly those origins and enables credentials. |

### Rate limiting

Fixed window, 60 requests per 60 seconds, counted per API key when one is presented and per client
address otherwise — so one noisy caller cannot exhaust everyone else's budget. Exceeding it returns
`429` with a `Retry-After` header. `/health`, `/docs`, `/openapi.json` and `/redoc` are exempt;
rate-limiting a health endpoint takes a service down under its own monitoring.

> **Single process only.** The counter lives in the server process, so behind multiple uvicorn
> workers each worker has its own and the effective limit is *per worker*. That matches the
> single-process default here; a horizontally scaled deployment needs a shared store (e.g. Redis)
> instead.

Request bodies are also bounded — `text` is capped at 50,000 characters (the same limit the scorer
uses) and anything longer is rejected with `422` rather than accepted and worked on.

## Endpoints

### `GET /health`

Health check. Returns version, detector tier, and available detectors.

```json
{
  "status": "ok",
  "version": "0.3.0",
  "detector_tier": "full",
  "detector_count": 5,
  "detectors": ["perplexity_burstiness", "roberta_openai", ...]
}
```

### `POST /score`

Score text with the local detector ensemble.

```json
{
  "text": "Your text here",
  "tier": "full",
  "threshold": 0.30
}
```

### `POST /humanize`

Run the closed-loop humanizer.

```json
{
  "text": "Your AI-sounding text here",
  "tier": "full",
  "threshold": 0.30,
  "style": "casual",
  "max_iters": 5,
  "rewriter": "composite",
  "best_of": 3,
  "margin": 0.0,
  "polish": false
}
```

### `POST /tells`

Count AI writing tells in text.

```json
{
  "text": "Your text here",
  "include_matches": false
}
```

### `POST /scrub`

Strip hidden watermark, zero-width and homoglyph characters. Returns `clean` and
`hidden_chars_removed`.

```json
{
  "text": "Your text here"
}
```

The CLI has `untell-scrub` and the MCP server has a `scrub` tool; this surface had neither, so a
REST caller holding untrusted text had no way to clean it. The characters do not move *this*
ensemble — normalised, verified at 0.0000 on both tiers — but the same text took an external
detector from 0.0002 to 0.7900 on those bytes alone.

### `POST /sentences`

Per-sentence AI scoring.

```json
{
  "text": "Your paragraph here.",
  "tier": "lite",
  "threshold": 0.30
}
```

### `POST /verify`

Pass/fail verification against commercial checkers + local ensemble.

```json
{
  "text": "Your text here",
  "threshold": 0.30,
  "tier": "full",
  "sandbox": false,
  "browser": null
}
```

### `POST /ceiling`

Measure the free evasion ceiling.

```json
{
  "tier": "full",
  "threshold": 0.30,
  "max_iters": 5,
  "rewriter": "surgical",
  "best_of": 1
}
```

## Authentication

If `UNTELL_API_KEY` is set, every request (except `/health`, `/docs`, `/openapi.json` and
`/redoc`) must include the key:

```
Authorization: Bearer ***
# or
X-API-Key: ***
```

CORS preflight requests (`OPTIONS`) are exempt too — browsers never attach credentials to a
preflight by spec; the real request carries the key. The `/openapi.json` schema declares both
schemes, so a client generated from it knows to send one.

## Deployment

### Docker

The repo ships a [Dockerfile](../Dockerfile) that builds the wheel from source and installs the
`server` extra; the image health-checks `/health` and binds all interfaces:

```dockerfile
FROM python:3.11-slim
RUN pip install "untell[server]"
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)" || exit 1
CMD ["sh", "-c", "exec untell-server --host 0.0.0.0 --port 8000"]
```

The image installs the `server` extra **only** (no `full`/torch) and defaults to the `lite`
tier, matching the Dockerfile's `ENV UNTELL_TIER="lite"` — the container answers the API without
pulling a model stack.

`/health` is exempt from auth and rate limiting, so a probe can never 401 or 429 itself into a
restart loop. The default bind is `127.0.0.1`, which is unreachable from outside a container —
pass `--host 0.0.0.0` (as above) when the container must answer on the network.

### Production

```bash
UNTELL_API_KEY=secret untell-server &
# or via process manager (supervisor, systemd)
```

See the FastAPI [deployment docs](https://fastapi.tiangolo.com/deployment/) for production best practices.
