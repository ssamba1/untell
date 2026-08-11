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
ENV UNTELL_API_KEY=""
ENV UNTELL_TIER="lite"
CMD ["sh", "-c", "exec untell-server --host 0.0.0.0 --port 8000"]
