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
RUN pip install --no-cache-dir /tmp/untell-*.whl[server] && rm /tmp/untell-*.whl

EXPOSE 8000
ENV UNTELL_API_KEY=""
ENV UNTELL_TIER="lite"
CMD ["sh", "-c", "exec untell-server --host 0.0.0.0 --port 8000"]
