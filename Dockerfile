# syntax=docker/dockerfile:1
FROM python:3.11-slim AS builder

WORKDIR /build
COPY . .
RUN pip install --no-cache-dir build && python -m build

FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /build/dist/*.whl /tmp/
# The wheel path is expanded BEFORE the extras are appended. Written as
# `pip install /tmp/untell-*.whl[server]`, the shell reads `[server]` as a glob character
# class, so the whole word only expands if a file matches `untell-*.whl` followed by one of
# s/e/r/v — which no wheel is, since wheels end at `.whl`. The pattern therefore never
# matches, the shell passes the literal string through, and pip fails with
# "untell-*.whl is not a valid wheel filename". No CI job builds this image, so it went
# unnoticed.
RUN WHEEL="$(ls /tmp/untell-*.whl)" \
    && pip install --no-cache-dir "${WHEEL}[server]" \
    && rm /tmp/untell-*.whl

EXPOSE 8000

# Cheap liveness probe for orchestrators. `/health` is exempt from auth and rate limiting (see
# api_server.py), so a probe can never 401 or 429 itself into a restart loop, and the endpoint is
# offloaded off the event loop so it answers promptly while a rewrite is running. `urllib` is
# stdlib — `curl` is not in python:3.11-slim and this image installs only ca-certificates. The
# server refuses to accept connections until lifespan's detector warm-up completes, so a probe
# either gets no connection (startup; covered by --start-period) or a fast answer.
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)" || exit 1

# Empty means NO AUTH, not "a key is configured". The server treats unset and empty the same
# way and serves every endpoint openly — verified: 200 without a header when this is "" or
# absent, 401 without and with a wrong header once it holds a value. Declared here so the
# variable is visible to `docker run -e`, but a container reachable from anywhere needs a real
# value passed in. `docs/api-server.md` documents the behaviour; the Dockerfile did not, and
# a declared API-key variable reads like auth is on.
ENV UNTELL_API_KEY=""
ENV UNTELL_TIER="lite"
CMD ["sh", "-c", "exec untell-server --host 0.0.0.0 --port 8000"]
