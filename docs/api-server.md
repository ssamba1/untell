# API Server

untell ships a production-grade REST API server built with **FastAPI** — auto-generated OpenAPI docs,
API-key auth, CORS support, and every endpoint from the CLI.

## Quick start

```bash
pip install "untell[server]"
UNTELL_API_KEY=my-secret-key untell-server
```

Open **http://localhost:8000/docs** for the interactive API documentation.

## Configuration

| Env var | Default | Description |
|---|---|---|
| `UNTELL_API_KEY` | *(none)* | API key for auth. Unset = open access. |
| `UNTELL_HOST` | `0.0.0.0` | Bind address |
| `UNTELL_PORT` | `8000` | Port |

## Endpoints

### `GET /health`

Health check. Returns version, detector tier, and available detectors.

```json
{
  "status": "ok",
  "version": "0.2.0",
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
  "tier": "lite",
  "threshold": 0.30,
  "style": "casual",
  "max_iters": 5,
  "rewriter": "surgical",
  "best_of": 1,
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

If `UNTELL_API_KEY` is set, every request (except `/health` and `/docs`) must include the key:

```
Authorization: Bearer <key>
# or
X-API-Key: <key>
```

## Deployment

### Docker

```dockerfile
FROM python:3.11-slim
RUN pip install "untell[full,server]"
EXPOSE 8000
CMD ["untell-server"]
```

### Production

```bash
UNTELL_API_KEY=secret untell-server &
# or via process manager (supervisor, systemd)
```

See the FastAPI [deployment docs](https://fastapi.tiangolo.com/deployment/) for production best practices.
