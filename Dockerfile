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

# Empty means NO AUTH, not "a key is configured". The server treats unset and empty the same
# way and serves every endpoint openly — verified: 200 without a header when this is "" or
# absent, 401 without and with a wrong header once it holds a value. Declared here so the
# variable is visible to `docker run -e`, but a container reachable from anywhere needs a real
# value passed in. `docs/api-server.md` documents the behaviour; the Dockerfile did not, and
# a declared API-key variable reads like auth is on.
ENV UNTELL_API_KEY=""
ENV UNTELL_TIER="lite"
CMD ["sh", "-c", "exec untell-server --host 0.0.0.0 --port 8000"]
